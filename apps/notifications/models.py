"""
Notification Models
"""
from django.db import models
from django.conf import settings
from apps.core.models import BaseModel


class Notification(BaseModel):
    """
    User notifications for various events.
    """
    
    class NotificationType(models.TextChoices):
        MENTION = 'mention', 'Mentioned in comment'
        COMMENT = 'comment', 'New comment'
        SHARE = 'share', 'Document shared'
        INVITE = 'invite', 'Workspace invitation'
        ASSIGNMENT = 'assignment', 'Assigned to task'
        DUE_DATE = 'due_date', 'Due date reminder'
        WORKSPACE = 'workspace', 'Workspace event'
        SYSTEM = 'system', 'System notification'
    
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    notification_type = models.CharField(
        max_length=20,
        choices=NotificationType.choices
    )
    
    # Actor (who triggered the notification)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='triggered_notifications'
    )
    
    # Title and message
    title = models.CharField(max_length=255)
    message = models.TextField()
    
    # Link/action
    action_url = models.CharField(max_length=500, blank=True)
    
    # Related object
    content_type = models.CharField(max_length=100, blank=True)
    object_id = models.UUIDField(null=True, blank=True)
    
    # Status
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True, null=True)
    
    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.notification_type} for {self.recipient.email}"
