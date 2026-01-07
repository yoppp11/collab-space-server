"""
WebSocket Consumers for Real-time Collaboration

Implements:
1. Document collaboration with CRDT sync
2. Presence awareness (active users, cursors)
3. Real-time notifications
"""
import json
import asyncio
import logging
from typing import Dict, Any
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.core.cache import cache
from django.utils import timezone
from asgiref.sync import sync_to_async

from apps.core.utils import IdempotencyService, get_redis_client
from apps.core.exceptions import PermissionDeniedError
from apps.workspaces.permissions import has_document_permission
from .services import (
    CollaborationService, PresenceService, 
    CRDTService, OperationProcessor
)

logger = logging.getLogger(__name__)


class DocumentConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time document collaboration.
    
    Handles:
    - User presence tracking
    - CRDT operations sync (Yjs/Automerge)
    - Cursor and selection updates
    - Block-level locking
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.document_id = None
        self.document_group = None
        self.user = None
        self.session_id = None
        self.user_color = None
    
    async def connect(self):
        """
        Handle WebSocket connection.
        """
        self.user = self.scope['user']
        self.document_id = self.scope['url_route']['kwargs']['document_id']
        self.document_group = f'document_{self.document_id}'
        
        # Authenticate user
        if not self.user or self.user.is_anonymous:
            logger.warning(f"Unauthenticated connection attempt to document {self.document_id}")
            await self.close(code=4001)
            return
        
        # Check document access permissions
        has_access = await self._check_document_access()
        if not has_access:
            logger.warning(f"User {self.user.id} denied access to document {self.document_id}")
            await self.close(code=4003)
            return
        
        # Accept connection
        await self.accept()
        
        # Join document room
        await self.channel_layer.group_add(
            self.document_group,
            self.channel_name
        )
        
        # Create collaboration session
        session_data = await self._create_session()
        self.session_id = session_data['session_id']
        self.user_color = session_data['color']
        
        # Send initial state to client
        await self.send_json({
            'type': 'connection.established',
            'data': {
                'session_id': self.session_id,
                'user_color': self.user_color,
                'document_state': await self._get_document_state(),
                'active_users': await self._get_active_users(),
            }
        })
        
        # Broadcast user joined to other users
        await self.channel_layer.group_send(
            self.document_group,
            {
                'type': 'user.joined',
                'user_id': str(self.user.id),
                'user_data': await self._get_user_data(),
            }
        )
        
        logger.info(f"User {self.user.id} connected to document {self.document_id}")
    
    async def disconnect(self, close_code):
        """
        Handle WebSocket disconnection.
        """
        if self.document_group and self.user:
            # Remove from group
            await self.channel_layer.group_discard(
                self.document_group,
                self.channel_name
            )
            
            # End collaboration session
            if self.session_id:
                await self._end_session()
            
            # Broadcast user left
            await self.channel_layer.group_send(
                self.document_group,
                {
                    'type': 'user.left',
                    'user_id': str(self.user.id),
                }
            )
            
            logger.info(f"User {self.user.id} disconnected from document {self.document_id}")
    
    async def receive(self, text_data):
        """
        Handle incoming WebSocket messages.
        """
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            message_id = data.get('id')
            payload = data.get('data', {})
            
            # Idempotency check
            if message_id:
                is_duplicate = await sync_to_async(IdempotencyService.is_duplicate)(message_id)
                if is_duplicate:
                    logger.debug(f"Duplicate message {message_id} ignored")
                    return
                await sync_to_async(IdempotencyService.mark_processed)(message_id)
            
            # Route message to appropriate handler
            handler = self._get_message_handler(message_type)
            if handler:
                await handler(payload, message_id)
            else:
                logger.warning(f"Unknown message type: {message_type}")
                await self.send_error(f"Unknown message type: {message_type}")
        
        except json.JSONDecodeError:
            await self.send_error("Invalid JSON")
        except Exception as e:
            logger.exception(f"Error processing message: {e}")
            await self.send_error("Internal server error")
    
    def _get_message_handler(self, message_type: str):
        """
        Map message type to handler method.
        """
        handlers = {
            'operation': self.handle_operation,
            'cursor': self.handle_cursor_update,
            'awareness': self.handle_awareness_update,
            'block.lock': self.handle_block_lock,
            'block.unlock': self.handle_block_unlock,
            'typing.start': self.handle_typing_start,
            'typing.stop': self.handle_typing_stop,
            'ping': self.handle_ping,
        }
        return handlers.get(message_type)
    
    async def handle_operation(self, payload: Dict, message_id: str):
        """
        Handle CRDT operation (Yjs/Automerge update).
        
        This is the critical path for conflict-free concurrent editing.
        """
        operation_data = payload.get('operation')
        client_version = payload.get('version')
        
        if not operation_data:
            await self.send_error("Missing operation data")
            return
        
        try:
            # Process operation through CRDT service
            result = await sync_to_async(OperationProcessor.process_operation)(
                document_id=self.document_id,
                user_id=str(self.user.id),
                operation_data=operation_data,
                client_version=client_version,
                message_id=message_id
            )
            
            if not result['success']:
                await self.send_error(result['error'])
                return
            
            # Broadcast operation to other users
            await self.channel_layer.group_send(
                self.document_group,
                {
                    'type': 'operation.broadcast',
                    'operation': result['operation'],
                    'version': result['version'],
                    'user_id': str(self.user.id),
                    'exclude_channel': self.channel_name,  # Don't send back to sender
                }
            )
            
            # Acknowledge to sender
            await self.send_json({
                'type': 'operation.ack',
                'id': message_id,
                'version': result['version'],
            })
        
        except Exception as e:
            logger.exception(f"Error processing operation: {e}")
            await self.send_error("Failed to process operation")
    
    async def handle_cursor_update(self, payload: Dict, message_id: str):
        """
        Handle cursor/selection position update.
        """
        cursor_data = {
            'position': payload.get('position'),
            'selection': payload.get('selection'),
            'block_id': payload.get('block_id'),
        }
        
        # Update presence in Redis
        await sync_to_async(PresenceService.update_cursor)(
            document_id=self.document_id,
            user_id=str(self.user.id),
            cursor_data=cursor_data
        )
        
        # Broadcast to other users
        await self.channel_layer.group_send(
            self.document_group,
            {
                'type': 'cursor.update',
                'user_id': str(self.user.id),
                'cursor': cursor_data,
                'exclude_channel': self.channel_name,
            }
        )
    
    async def handle_awareness_update(self, payload: Dict, message_id: str):
        """
        Handle general awareness state update (Yjs awareness).
        """
        awareness_data = payload.get('state', {})
        
        await sync_to_async(PresenceService.update_awareness)(
            document_id=self.document_id,
            user_id=str(self.user.id),
            state=awareness_data
        )
        
        # Broadcast to other users
        await self.channel_layer.group_send(
            self.document_group,
            {
                'type': 'awareness.update',
                'user_id': str(self.user.id),
                'state': awareness_data,
                'exclude_channel': self.channel_name,
            }
        )
    
    async def handle_block_lock(self, payload: Dict, message_id: str):
        """
        Acquire lock on a block for editing.
        """
        block_id = payload.get('block_id')
        
        if not block_id:
            await self.send_error("Missing block_id")
            return
        
        success = await sync_to_async(CollaborationService.acquire_block_lock)(
            document_id=self.document_id,
            block_id=block_id,
            user_id=str(self.user.id)
        )
        
        if success:
            # Notify all users about the lock
            await self.channel_layer.group_send(
                self.document_group,
                {
                    'type': 'block.locked',
                    'block_id': block_id,
                    'user_id': str(self.user.id),
                }
            )
        else:
            await self.send_error(f"Block {block_id} is already locked")
    
    async def handle_block_unlock(self, payload: Dict, message_id: str):
        """
        Release lock on a block.
        """
        block_id = payload.get('block_id')
        
        if not block_id:
            await self.send_error("Missing block_id")
            return
        
        await sync_to_async(CollaborationService.release_block_lock)(
            document_id=self.document_id,
            block_id=block_id,
            user_id=str(self.user.id)
        )
        
        # Notify all users about the unlock
        await self.channel_layer.group_send(
            self.document_group,
            {
                'type': 'block.unlocked',
                'block_id': block_id,
                'user_id': str(self.user.id),
            }
        )
    
    async def handle_typing_start(self, payload: Dict, message_id: str):
        """
        User started typing indicator.
        """
        block_id = payload.get('block_id')
        
        await self.channel_layer.group_send(
            self.document_group,
            {
                'type': 'typing.started',
                'user_id': str(self.user.id),
                'block_id': block_id,
                'exclude_channel': self.channel_name,
            }
        )
    
    async def handle_typing_stop(self, payload: Dict, message_id: str):
        """
        User stopped typing indicator.
        """
        block_id = payload.get('block_id')
        
        await self.channel_layer.group_send(
            self.document_group,
            {
                'type': 'typing.stopped',
                'user_id': str(self.user.id),
                'block_id': block_id,
                'exclude_channel': self.channel_name,
            }
        )
    
    async def handle_ping(self, payload: Dict, message_id: str):
        """
        Keep-alive ping.
        """
        # Update last activity
        await sync_to_async(PresenceService.update_activity)(
            document_id=self.document_id,
            user_id=str(self.user.id)
        )
        
        await self.send_json({
            'type': 'pong',
            'timestamp': timezone.now().isoformat(),
        })
    
    # =========================================================================
    # Group message handlers (receive broadcasts from channel layer)
    # =========================================================================
    
    async def operation_broadcast(self, event):
        """
        Broadcast operation to client (from other users).
        """
        if event.get('exclude_channel') == self.channel_name:
            return
        
        await self.send_json({
            'type': 'operation',
            'data': {
                'operation': event['operation'],
                'version': event['version'],
                'user_id': event['user_id'],
            }
        })
    
    async def cursor_update(self, event):
        """
        Broadcast cursor update to client.
        """
        if event.get('exclude_channel') == self.channel_name:
            return
        
        await self.send_json({
            'type': 'cursor.update',
            'data': {
                'user_id': event['user_id'],
                'cursor': event['cursor'],
            }
        })
    
    async def awareness_update(self, event):
        """
        Broadcast awareness update to client.
        """
        if event.get('exclude_channel') == self.channel_name:
            return
        
        await self.send_json({
            'type': 'awareness',
            'data': {
                'user_id': event['user_id'],
                'state': event['state'],
            }
        })
    
    async def user_joined(self, event):
        """
        Notify client that a user joined.
        """
        await self.send_json({
            'type': 'user.joined',
            'data': event['user_data']
        })
    
    async def user_left(self, event):
        """
        Notify client that a user left.
        """
        await self.send_json({
            'type': 'user.left',
            'data': {
                'user_id': event['user_id']
            }
        })
    
    async def block_locked(self, event):
        """
        Notify client that a block was locked.
        """
        await self.send_json({
            'type': 'block.locked',
            'data': {
                'block_id': event['block_id'],
                'user_id': event['user_id'],
            }
        })
    
    async def block_unlocked(self, event):
        """
        Notify client that a block was unlocked.
        """
        await self.send_json({
            'type': 'block.unlocked',
            'data': {
                'block_id': event['block_id'],
                'user_id': event['user_id'],
            }
        })
    
    async def typing_started(self, event):
        """
        Notify client that a user started typing.
        """
        if event.get('exclude_channel') == self.channel_name:
            return
        
        await self.send_json({
            'type': 'typing.start',
            'data': {
                'user_id': event['user_id'],
                'block_id': event.get('block_id'),
            }
        })
    
    async def typing_stopped(self, event):
        """
        Notify client that a user stopped typing.
        """
        if event.get('exclude_channel') == self.channel_name:
            return
        
        await self.send_json({
            'type': 'typing.stop',
            'data': {
                'user_id': event['user_id'],
                'block_id': event.get('block_id'),
            }
        })
    
    # =========================================================================
    # Helper methods
    # =========================================================================
    
    async def send_json(self, content):
        """
        Send JSON message to client.
        """
        await self.send(text_data=json.dumps(content))
    
    async def send_error(self, message: str):
        """
        Send error message to client.
        """
        await self.send_json({
            'type': 'error',
            'error': {
                'message': message
            }
        })
    
    @database_sync_to_async
    def _check_document_access(self) -> bool:
        """
        Check if user has access to the document.
        """
        from apps.documents.models import Document
        from apps.workspaces.models import Workspace
        
        try:
            document = Document.objects.select_related('workspace').get(
                id=self.document_id,
                is_deleted=False
            )
            
            # Check if user has view permission
            return has_document_permission(self.user, document, 'can_view')
        except Document.DoesNotExist:
            return False
    
    @database_sync_to_async
    def _create_session(self) -> Dict:
        """
        Create a collaboration session.
        """
        return CollaborationService.create_session(
            document_id=self.document_id,
            user_id=str(self.user.id),
            channel_name=self.channel_name
        )
    
    @database_sync_to_async
    def _end_session(self):
        """
        End collaboration session.
        """
        CollaborationService.end_session(
            document_id=self.document_id,
            user_id=str(self.user.id)
        )
    
    @database_sync_to_async
    def _get_document_state(self) -> Dict:
        """
        Get current document state for initial sync.
        """
        return CRDTService.get_document_state(self.document_id)
    
    @database_sync_to_async
    def _get_active_users(self) -> list:
        """
        Get list of currently active users on this document.
        """
        return PresenceService.get_active_users(self.document_id)
    
    @database_sync_to_async
    def _get_user_data(self) -> Dict:
        """
        Get serialized user data for presence.
        """
        from apps.users.serializers import UserPublicSerializer
        return {
            **UserPublicSerializer(self.user).data,
            'color': self.user_color,
            'session_id': self.session_id,
        }


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time notifications.
    """
    
    async def connect(self):
        self.user = self.scope['user']
        
        if not self.user or self.user.is_anonymous:
            await self.close(code=4001)
            return
        
        self.user_group = f'user_{self.user.id}'
        
        await self.accept()
        await self.channel_layer.group_add(
            self.user_group,
            self.channel_name
        )
    
    async def disconnect(self, close_code):
        if hasattr(self, 'user_group'):
            await self.channel_layer.group_discard(
                self.user_group,
                self.channel_name
            )
    
    async def notification(self, event):
        """
        Send notification to client.
        """
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'data': event['data']
        }))


class WorkspaceConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time workspace updates.
    
    Handles:
    - Board creation/updates/deletion
    - Member joins/leaves
    - Workspace settings changes
    - Card updates on boards
    """
    
    async def connect(self):
        self.user = self.scope['user']
        self.workspace_id = self.scope['url_route']['kwargs']['workspace_id']
        self.workspace_group = f'workspace_{self.workspace_id}'
        
        # Authenticate user
        if not self.user or self.user.is_anonymous:
            logger.warning(f"Unauthenticated connection attempt to workspace {self.workspace_id}")
            await self.close(code=4001)
            return
        
        # Check workspace access permissions
        has_access = await self._check_workspace_access()
        if not has_access:
            logger.warning(f"User {self.user.id} denied access to workspace {self.workspace_id}")
            await self.close(code=4003)
            return
        
        # Accept connection
        await self.accept()
        
        # Join workspace room
        await self.channel_layer.group_add(
            self.workspace_group,
            self.channel_name
        )
        
        logger.info(f"User {self.user.id} connected to workspace {self.workspace_id}")
    
    async def disconnect(self, close_code):
        # Leave workspace room
        if hasattr(self, 'workspace_group'):
            await self.channel_layer.group_discard(
                self.workspace_group,
                self.channel_name
            )
            logger.info(f"User {self.user.id} disconnected from workspace {self.workspace_id}")
    
    @database_sync_to_async
    def _check_workspace_access(self):
        """Check if user has access to this workspace."""
        from apps.workspaces.models import WorkspaceMembership
        return WorkspaceMembership.objects.filter(
            workspace_id=self.workspace_id,
            user_id=self.user.id,
            is_active=True
        ).exists()
    
    # Event handlers for different types of workspace updates
    
    async def board_created(self, event):
        """Broadcast board creation to all workspace members."""
        await self.send(text_data=json.dumps({
            'type': 'board.created',
            'data': event['data']
        }))
    
    async def board_updated(self, event):
        """Broadcast board updates to all workspace members."""
        await self.send(text_data=json.dumps({
            'type': 'board.updated',
            'data': event['data']
        }))
    
    async def board_deleted(self, event):
        """Broadcast board deletion to all workspace members."""
        await self.send(text_data=json.dumps({
            'type': 'board.deleted',
            'data': event['data']
        }))
    
    async def member_joined(self, event):
        """Broadcast member join to all workspace members."""
        await self.send(text_data=json.dumps({
            'type': 'member.joined',
            'data': event['data']
        }))
    
    async def member_left(self, event):
        """Broadcast member leave to all workspace members."""
        await self.send(text_data=json.dumps({
            'type': 'member.left',
            'data': event['data']
        }))
    
    async def member_role_updated(self, event):
        """Broadcast member role update to all workspace members."""
        await self.send(text_data=json.dumps({
            'type': 'member.role_updated',
            'data': event['data']
        }))
    
    async def card_created(self, event):
        """Broadcast card creation to all workspace members."""
        await self.send(text_data=json.dumps({
            'type': 'card.created',
            'data': event['data']
        }))
    
    async def card_updated(self, event):
        """Broadcast card updates to all workspace members."""
        await self.send(text_data=json.dumps({
            'type': 'card.updated',
            'data': event['data']
        }))
    
    async def card_comment_created(self, event):
        """Broadcast card comment creation to all workspace members."""
        await self.send(text_data=json.dumps({
            'type': 'card.comment_created',
            'data': event['data']
        }))
