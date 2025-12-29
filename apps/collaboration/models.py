"""
Real-time Collaboration Models

Tracks real-time presence, cursors, and collaborative editing sessions.
"""
from django.db import models
from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from apps.core.models import BaseModel


class CollaborationSession(BaseModel):
    """
    Tracks active collaboration sessions on documents.
    """
    
    document = models.ForeignKey(
        'documents.Document',
        on_delete=models.CASCADE,
        related_name='collaboration_sessions'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='collaboration_sessions'
    )
    
    # WebSocket connection info
    channel_name = models.CharField(max_length=255)
    
    # User's current state
    is_active = models.BooleanField(default=True)
    last_activity = models.DateTimeField(auto_now=True)
    
    # Cursor/selection position
    cursor_position = models.JSONField(
        default=dict,
        blank=True,
        help_text='Current cursor position in document'
    )
    
    # Current block being edited
    current_block_id = models.UUIDField(null=True, blank=True)
    
    # User's color for collaborative indicators
    color = models.CharField(max_length=7, default='#6366f1')
    
    class Meta:
        db_table = 'collaboration_sessions'
        indexes = [
            models.Index(fields=['document', 'is_active']),
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['last_activity']),
        ]
    
    def __str__(self):
        return f"{self.user.email} on {self.document.title}"


class OperationLog(BaseModel):
    """
    Log of operations for Operational Transformation / CRDT.
    Enables conflict-free merging and replay.
    """
    
    document = models.ForeignKey(
        'documents.Document',
        on_delete=models.CASCADE,
        related_name='operations'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='operations'
    )
    
    # Operation metadata
    operation_id = models.CharField(max_length=100, unique=True, db_index=True)
    operation_type = models.CharField(
        max_length=50,
        help_text='insert, delete, update, move, etc.'
    )
    
    # Operation payload (Yjs/Automerge update)
    payload = models.BinaryField(
        help_text='CRDT update in binary format'
    )
    
    # Context for ordering
    version = models.PositiveIntegerField(db_index=True)
    client_id = models.CharField(max_length=100)
    
    # Timestamp for conflict resolution
    timestamp = models.BigIntegerField(
        db_index=True,
        help_text='High-precision timestamp for ordering'
    )
    
    class Meta:
        db_table = 'operation_logs'
        ordering = ['version', 'timestamp']
        indexes = [
            models.Index(fields=['document', 'version']),
            models.Index(fields=['operation_id']),
            models.Index(fields=['timestamp']),
        ]
    
    def __str__(self):
        return f"{self.operation_type} v{self.version} by {self.user.email}"


class PresenceAwareness(models.Model):
    """
    Real-time presence awareness state.
    Stored in Redis with periodic snapshots to DB.
    """
    
    id = models.CharField(max_length=100, primary_key=True)
    document_id = models.UUIDField(db_index=True)
    user_id = models.UUIDField(db_index=True)
    
    # Awareness state
    state = models.JSONField(
        default=dict,
        help_text='User awareness state (cursor, selection, etc.)'
    )
    
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'presence_awareness'
        indexes = [
            models.Index(fields=['document_id', 'user_id']),
        ]
