"""
Notification Services
"""
from typing import Optional
from django.contrib.auth import get_user_model
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import Notification

User = get_user_model()


class NotificationService:
    """
    Service for creating and sending notifications.
    """
    
    @staticmethod
    def create_notification(
        recipient,
        notification_type: str,
        title: str,
        message: str,
        actor=None,
        action_url: str = '',
        content_type: str = '',
        object_id: str = None,
        metadata: dict = None
    ) -> Notification:
        """
        Create a notification.
        """
        notification = Notification.objects.create(
            recipient=recipient,
            notification_type=notification_type,
            title=title,
            message=message,
            actor=actor,
            action_url=action_url,
            content_type=content_type,
            object_id=object_id,
            metadata=metadata or {}
        )
        
        # Send real-time notification via WebSocket
        NotificationService.send_realtime_notification(notification)
        
        return notification
    
    @staticmethod
    def send_realtime_notification(notification: Notification):
        """
        Send notification via WebSocket to connected clients.
        """
        from .serializers import NotificationSerializer
        
        channel_layer = get_channel_layer()
        user_group = f'user_{notification.recipient_id}'
        
        async_to_sync(channel_layer.group_send)(
            user_group,
            {
                'type': 'notification',
                'data': NotificationSerializer(notification).data
            }
        )
    
    @staticmethod
    def notify_mention(mentioned_user, mentioner, document, comment):
        """
        Notify user when mentioned in a comment.
        """
        return NotificationService.create_notification(
            recipient=mentioned_user,
            notification_type=Notification.NotificationType.MENTION,
            title=f"{mentioner.display_name} mentioned you",
            message=f'In "{document.title}": {comment.text[:100]}',
            actor=mentioner,
            action_url=f'/documents/{document.id}#comment-{comment.id}',
            content_type='comment',
            object_id=comment.id
        )
    
    @staticmethod
    def notify_comment(recipient, commenter, document, comment):
        """
        Notify user of a new comment on their document.
        """
        return NotificationService.create_notification(
            recipient=recipient,
            notification_type=Notification.NotificationType.COMMENT,
            title=f"{commenter.display_name} commented",
            message=f'On "{document.title}": {comment.text[:100]}',
            actor=commenter,
            action_url=f'/documents/{document.id}#comment-{comment.id}',
            content_type='comment',
            object_id=comment.id
        )
