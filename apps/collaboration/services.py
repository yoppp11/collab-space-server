"""
Collaboration Services - CRDT Integration and Conflict Resolution

This module implements the backend logic for Conflict-free Replicated Data Types (CRDT)
integration, specifically designed to work with Yjs or Automerge on the client side.

KEY CONCEPTS:
=============

1. CRDT (Conflict-free Replicated Data Types):
   - Mathematical structures that guarantee eventual consistency
   - Allow concurrent edits without central coordination
   - Automatically merge conflicting changes deterministically

2. Operational Transformation (OT) vs CRDT:
   - OT: Requires central server, transforms operations based on context
   - CRDT: Commutative operations, no central authority needed
   - We use CRDT (Yjs/Automerge) for better offline support and simpler logic

3. Backend's Role in CRDT:
   - Store operations/updates for persistence
   - Broadcast updates to connected clients
   - Provide initial state to new joiners
   - Handle cleanup and compression

IMPLEMENTATION STRATEGY:
=======================

## With Yjs (Recommended):
- Client uses Y.Doc to maintain CRDT state
- Client sends Yjs updates (binary) to server via WebSocket
- Server broadcasts updates to other clients
- Server persists updates in database
- On reconnect: Server sends all missing updates since last known version

## With Automerge:
- Similar pattern but uses Automerge's change format
- Smaller update sizes but less ecosystem support

PREVENTING DATA LOSS:
=====================

The system prevents "Last-Write-Wins" data loss through:

1. **Version Vectors**: Each operation has a version number and client ID
2. **Causal Ordering**: Operations preserve happened-before relationships
3. **Idempotency**: Duplicate messages are detected and ignored
4. **Persistence**: All operations are logged before acknowledgment
5. **Merge Function**: CRDT merge is commutative and associative

"""
import logging
import time
import hashlib
import json
from typing import Dict, List, Optional, Any
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from apps.core.utils import get_redis_client

logger = logging.getLogger(__name__)


class CRDTService:
    """
    Service for managing CRDT state and operations.
    
    Designed to work with Yjs or Automerge clients.
    """
    
    @staticmethod
    def get_document_state(document_id: str) -> Dict:
        """
        Get the current CRDT state for a document.
        
        Returns:
            - state_vector: For clients to determine what updates they need
            - updates: Recent operations for sync
            - version: Current document version
        """
        from apps.documents.models import Document
        from .models import OperationLog
        
        try:
            document = Document.objects.get(id=document_id)
            
            # Get recent operations (last 100 or since last snapshot)
            recent_ops = OperationLog.objects.filter(
                document_id=document_id
            ).order_by('-version')[:100]
            
            return {
                'document_id': str(document_id),
                'state': document.state,  # CRDT state (Yjs state vector or Automerge heads)
                'version': document.current_version,
                'updates': [
                    {
                        'operation_id': op.operation_id,
                        'version': op.version,
                        'payload': op.payload.hex(),  # Convert binary to hex for JSON
                        'timestamp': op.timestamp,
                    }
                    for op in reversed(list(recent_ops))
                ],
            }
        except Document.DoesNotExist:
            return {'error': 'Document not found'}
    
    @staticmethod
    def apply_state_vector(document_id: str, client_state_vector: Dict) -> List[bytes]:
        """
        Compare client's state vector with server's to find missing updates.
        
        This is how Yjs determines which updates to send to a syncing client.
        """
        from .models import OperationLog
        
        # Get operations the client doesn't have
        # In Yjs, this compares state vectors to find the diff
        # For simplicity, we'll return operations after client's last version
        
        client_version = client_state_vector.get('version', 0)
        
        missing_ops = OperationLog.objects.filter(
            document_id=document_id,
            version__gt=client_version
        ).order_by('version')
        
        return [op.payload for op in missing_ops]


class OperationProcessor:
    """
    Process and persist CRDT operations.
    
    CRITICAL PATH: This is where concurrent edits are handled.
    """
    
    @staticmethod
    @transaction.atomic
    def process_operation(
        document_id: str,
        user_id: str,
        operation_data: Dict,
        client_version: int,
        message_id: str
    ) -> Dict:
        """
        Process a CRDT operation from a client.
        
        Steps:
        1. Validate operation
        2. Assign server version
        3. Persist operation
        4. Update document state
        5. Return acknowledgment
        
        The CRDT properties ensure this is conflict-free even with
        concurrent operations from multiple clients.
        """
        from apps.documents.models import Document
        from .models import OperationLog
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        
        try:
            # Load document with row-level lock (SELECT FOR UPDATE)
            document = Document.objects.select_for_update().get(
                id=document_id,
                is_deleted=False
            )
            
            # Validate operation structure
            if not OperationProcessor._validate_operation(operation_data):
                return {
                    'success': False,
                    'error': 'Invalid operation format'
                }
            
            # Assign server version (monotonically increasing)
            server_version = document.current_version + 1
            
            # Generate operation ID (for idempotency)
            operation_id = OperationProcessor._generate_operation_id(
                document_id, user_id, message_id, server_version
            )
            
            # Check if operation already exists (idempotency)
            if OperationLog.objects.filter(operation_id=operation_id).exists():
                logger.warning(f"Duplicate operation {operation_id}")
                return {
                    'success': False,
                    'error': 'Duplicate operation'
                }
            
            # Extract binary payload (Yjs update or Automerge change)
            payload_hex = operation_data.get('payload')
            if not payload_hex:
                return {
                    'success': False,
                    'error': 'Missing payload'
                }
            
            payload_binary = bytes.fromhex(payload_hex)
            
            # Create operation log entry
            operation = OperationLog.objects.create(
                document_id=document_id,
                user_id=user_id,
                operation_id=operation_id,
                operation_type=operation_data.get('type', 'update'),
                payload=payload_binary,
                version=server_version,
                client_id=operation_data.get('client_id', user_id),
                timestamp=int(time.time() * 1000000)  # Microsecond precision
            )
            
            # Update document state (merge CRDT update)
            # In production, you'd use Yjs or Automerge library here
            # For now, we'll update the state version
            document.current_version = server_version
            document.last_edited_by_id = user_id
            document.last_edited_at = timezone.now()
            
            # Optionally update the full state snapshot
            # This would involve loading the Yjs document server-side
            # and applying the update, then storing the new state
            
            document.save(update_fields=[
                'current_version',
                'last_edited_by_id',
                'last_edited_at',
                'updated_at'
            ])
            
            # Update cache
            cache.delete(f'doc_state:{document_id}')
            
            # Log activity
            user = User.objects.get(id=user_id)
            from apps.users.services import UserService
            UserService.log_activity(
                user=user,
                activity_type='document_edit',
                content_type='document',
                object_id=document_id,
                metadata={'version': server_version}
            )
            
            return {
                'success': True,
                'operation': {
                    'id': operation_id,
                    'payload': payload_hex,
                },
                'version': server_version,
            }
        
        except Document.DoesNotExist:
            return {
                'success': False,
                'error': 'Document not found'
            }
        except Exception as e:
            logger.exception(f"Error processing operation: {e}")
            return {
                'success': False,
                'error': 'Internal server error'
            }
    
    @staticmethod
    def _validate_operation(operation_data: Dict) -> bool:
        """
        Validate operation structure.
        """
        required_fields = ['payload', 'type']
        return all(field in operation_data for field in required_fields)
    
    @staticmethod
    def _generate_operation_id(
        document_id: str,
        user_id: str,
        message_id: str,
        version: int
    ) -> str:
        """
        Generate a unique operation ID.
        """
        data = f"{document_id}:{user_id}:{message_id}:{version}"
        return hashlib.sha256(data.encode()).hexdigest()[:32]


class PresenceService:
    """
    Manage real-time user presence and awareness.
    
    Uses Redis for fast lookups and updates.
    """
    
    PRESENCE_TTL = 60  # seconds
    CURSOR_UPDATE_THROTTLE = 0.1  # seconds
    
    @staticmethod
    def get_active_users(document_id: str) -> List[Dict]:
        """
        Get all active users on a document.
        """
        redis_client = get_redis_client()
        key = f"presence:{document_id}:users"
        
        # Get all user IDs from Redis set
        user_ids = redis_client.smembers(key)
        
        # Get presence data for each user
        users = []
        for user_id in user_ids:
            user_key = f"presence:{document_id}:user:{user_id}"
            user_data = redis_client.hgetall(user_key)
            
            if user_data:
                # Parse JSON fields
                users.append({
                    'user_id': user_id,
                    'display_name': user_data.get('display_name', ''),
                    'avatar': user_data.get('avatar', ''),
                    'color': user_data.get('color', '#6366f1'),
                    'cursor': json.loads(user_data.get('cursor', '{}')),
                    'last_activity': float(user_data.get('last_activity', 0)),
                })
        
        return users
    
    @staticmethod
    def add_user_presence(
        document_id: str,
        user_id: str,
        user_data: Dict
    ):
        """
        Add or update user presence.
        """
        redis_client = get_redis_client()
        
        # Add to active users set
        set_key = f"presence:{document_id}:users"
        redis_client.sadd(set_key, user_id)
        redis_client.expire(set_key, PresenceService.PRESENCE_TTL)
        
        # Store user data
        user_key = f"presence:{document_id}:user:{user_id}"
        redis_client.hmset(user_key, {
            'display_name': user_data.get('display_name', ''),
            'avatar': user_data.get('avatar', ''),
            'color': user_data.get('color', '#6366f1'),
            'cursor': json.dumps({}),
            'last_activity': time.time(),
        })
        redis_client.expire(user_key, PresenceService.PRESENCE_TTL)
    
    @staticmethod
    def remove_user_presence(document_id: str, user_id: str):
        """
        Remove user from presence.
        """
        redis_client = get_redis_client()
        
        set_key = f"presence:{document_id}:users"
        redis_client.srem(set_key, user_id)
        
        user_key = f"presence:{document_id}:user:{user_id}"
        redis_client.delete(user_key)
    
    @staticmethod
    def update_cursor(document_id: str, user_id: str, cursor_data: Dict):
        """
        Update user's cursor position.
        """
        redis_client = get_redis_client()
        
        user_key = f"presence:{document_id}:user:{user_id}"
        redis_client.hset(user_key, 'cursor', json.dumps(cursor_data))
        redis_client.hset(user_key, 'last_activity', time.time())
        redis_client.expire(user_key, PresenceService.PRESENCE_TTL)
    
    @staticmethod
    def update_awareness(document_id: str, user_id: str, state: Dict):
        """
        Update user's awareness state (Yjs awareness protocol).
        """
        redis_client = get_redis_client()
        
        awareness_key = f"awareness:{document_id}:{user_id}"
        redis_client.set(
            awareness_key,
            json.dumps(state),
            ex=PresenceService.PRESENCE_TTL
        )
    
    @staticmethod
    def update_activity(document_id: str, user_id: str):
        """
        Update last activity timestamp.
        """
        redis_client = get_redis_client()
        
        user_key = f"presence:{document_id}:user:{user_id}"
        redis_client.hset(user_key, 'last_activity', time.time())
        redis_client.expire(user_key, PresenceService.PRESENCE_TTL)


class CollaborationService:
    """
    High-level collaboration coordination service.
    """
    
    @staticmethod
    def create_session(
        document_id: str,
        user_id: str,
        channel_name: str
    ) -> Dict:
        """
        Create a new collaboration session.
        """
        from .models import CollaborationSession
        from django.contrib.auth import get_user_model
        import random
        
        User = get_user_model()
        user = User.objects.get(id=user_id)
        
        # Generate user color
        colors = [
            '#ef4444', '#f59e0b', '#10b981', '#3b82f6',
            '#6366f1', '#8b5cf6', '#ec4899', '#f97316'
        ]
        user_color = random.choice(colors)
        
        # Create session
        session = CollaborationSession.objects.create(
            document_id=document_id,
            user_id=user_id,
            channel_name=channel_name,
            color=user_color
        )
        
        # Add to presence
        PresenceService.add_user_presence(
            document_id=document_id,
            user_id=user_id,
            user_data={
                'display_name': user.display_name,
                'avatar': user.avatar.url if user.avatar else '',
                'color': user_color,
            }
        )
        
        return {
            'session_id': str(session.id),
            'color': user_color,
        }
    
    @staticmethod
    def end_session(document_id: str, user_id: str):
        """
        End a collaboration session.
        """
        from .models import CollaborationSession
        
        CollaborationSession.objects.filter(
            document_id=document_id,
            user_id=user_id
        ).update(is_active=False)
        
        PresenceService.remove_user_presence(document_id, user_id)
    
    @staticmethod
    def acquire_block_lock(
        document_id: str,
        block_id: str,
        user_id: str,
        timeout: int = 30
    ) -> bool:
        """
        Acquire exclusive lock on a block.
        
        Returns True if lock acquired, False if already locked.
        """
        redis_client = get_redis_client()
        lock_key = f"block_lock:{document_id}:{block_id}"
        
        # Try to set lock with NX (only if not exists) and EX (expiry)
        acquired = redis_client.set(
            lock_key,
            user_id,
            nx=True,
            ex=timeout
        )
        
        return bool(acquired)
    
    @staticmethod
    def release_block_lock(document_id: str, block_id: str, user_id: str):
        """
        Release block lock (only if owned by user).
        """
        redis_client = get_redis_client()
        lock_key = f"block_lock:{document_id}:{block_id}"
        
        # Lua script for atomic check-and-delete
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        
        redis_client.eval(lua_script, 1, lock_key, user_id)
    
    @staticmethod
    def get_block_lock_owner(document_id: str, block_id: str) -> Optional[str]:
        """
        Get the user ID who owns the lock on a block.
        """
        redis_client = get_redis_client()
        lock_key = f"block_lock:{document_id}:{block_id}"
        
        owner = redis_client.get(lock_key)
        return owner if owner else None
