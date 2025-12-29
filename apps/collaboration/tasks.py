"""
Collaboration Celery Tasks
"""
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task
def cleanup_expired_sessions():
    """
    Clean up inactive collaboration sessions.
    Runs every 5 minutes via Celery Beat.
    """
    from .models import CollaborationSession
    
    cutoff_time = timezone.now() - timedelta(minutes=5)
    
    expired_count = CollaborationSession.objects.filter(
        last_activity__lt=cutoff_time,
        is_active=True
    ).update(is_active=False)
    
    logger.info(f"Cleaned up {expired_count} expired collaboration sessions")
    return expired_count


@shared_task
def compress_operation_logs(document_id: str):
    """
    Compress old operation logs by creating a snapshot.
    
    CRDT systems accumulate operations over time. Periodically, we can
    create a snapshot of the current state and delete old operations.
    """
    from .models import OperationLog
    from apps.documents.models import Document
    
    try:
        document = Document.objects.get(id=document_id)
        
        # Get operation count
        op_count = OperationLog.objects.filter(document_id=document_id).count()
        
        # If we have more than 1000 operations, compress
        if op_count > 1000:
            # In a real implementation with Yjs:
            # 1. Load all operations
            # 2. Apply them to a Y.Doc
            # 3. Create a state snapshot
            # 4. Delete operations older than the snapshot
            # 5. Store the snapshot
            
            # For now, we'll just keep last 500 operations
            old_ops = OperationLog.objects.filter(
                document_id=document_id
            ).order_by('-version')[500:]
            
            deleted_count = old_ops.delete()[0]
            
            logger.info(f"Compressed {deleted_count} operations for document {document_id}")
            return deleted_count
        
        return 0
    except Document.DoesNotExist:
        logger.error(f"Document {document_id} not found")
        return 0


@shared_task
def sync_presence_to_db():
    """
    Periodically sync Redis presence data to database.
    This provides a backup and allows for analytics.
    """
    from apps.core.utils import get_redis_client
    from .models import PresenceAwareness
    import json
    
    redis_client = get_redis_client()
    
    # Find all presence keys
    cursor = 0
    synced_count = 0
    
    while True:
        cursor, keys = redis_client.scan(
            cursor=cursor,
            match="presence:*:user:*",
            count=100
        )
        
        for key in keys:
            # Parse key: presence:{doc_id}:user:{user_id}
            parts = key.split(':')
            if len(parts) >= 4:
                doc_id = parts[1]
                user_id = parts[3]
                
                user_data = redis_client.hgetall(key)
                if user_data:
                    # Upsert to database
                    PresenceAwareness.objects.update_or_create(
                        id=f"{doc_id}:{user_id}",
                        defaults={
                            'document_id': doc_id,
                            'user_id': user_id,
                            'state': {
                                'cursor': json.loads(user_data.get('cursor', '{}')),
                                'color': user_data.get('color', '#6366f1'),
                                'last_activity': float(user_data.get('last_activity', 0)),
                            }
                        }
                    )
                    synced_count += 1
        
        if cursor == 0:
            break
    
    logger.info(f"Synced {synced_count} presence records to database")
    return synced_count
