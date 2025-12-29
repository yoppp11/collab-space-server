"""
Document Models - Block-based Hierarchical Structure

Implements a Notion-style block-based document system with:
- Nested blocks (using django-mptt)
- Document versioning
- Granular permissions
- Collaborative editing tracking
"""
from django.db import models
from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from mptt.models import MPTTModel, TreeForeignKey
from apps.core.models import BaseModel, SoftDeleteModel, SoftDeleteManager, OrderedModel


class Document(BaseModel, SoftDeleteModel):
    """
    Top-level document container.
    """
    
    workspace = models.ForeignKey(
        'workspaces.Workspace',
        on_delete=models.CASCADE,
        related_name='documents'
    )
    board = models.ForeignKey(
        'workspaces.Board',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='documents'
    )
    board_list = models.ForeignKey(
        'workspaces.BoardList',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cards'
    )
    
    # Metadata
    title = models.CharField(max_length=500, default='Untitled')
    icon = models.CharField(max_length=50, blank=True)
    cover_image = models.ImageField(
        upload_to='document_covers/%Y/%m/',
        blank=True,
        null=True
    )
    cover_position = models.FloatField(default=0.5)
    
    # Creator and ownership
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_documents'
    )
    
    # Collaboration
    last_edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='last_edited_documents'
    )
    last_edited_at = models.DateTimeField(auto_now=True)
    
    # Document state stored as JSONB for flexibility
    # This can store Yjs/Automerge state
    state = models.JSONField(
        default=dict,
        blank=True,
        help_text='Collaborative editing state (CRDT)'
    )
    
    # Version tracking
    current_version = models.PositiveIntegerField(default=1)
    
    # Document settings
    is_template = models.BooleanField(default=False)
    is_locked = models.BooleanField(
        default=False,
        help_text='Locked documents cannot be edited'
    )
    is_public = models.BooleanField(default=False)
    
    # Metadata
    tags = ArrayField(
        models.CharField(max_length=50),
        default=list,
        blank=True
    )
    
    # For Trello-style cards
    position = models.FloatField(default=0, db_index=True)
    due_date = models.DateTimeField(null=True, blank=True)
    
    # Document properties as JSONB (Notion-style)
    properties = models.JSONField(
        default=dict,
        blank=True,
        help_text='Custom properties (select, multi-select, date, etc.)'
    )
    
    objects = SoftDeleteManager()
    
    class Meta:
        db_table = 'documents'
        indexes = [
            models.Index(fields=['workspace', 'is_deleted']),
            models.Index(fields=['board', 'board_list', 'position']),
            models.Index(fields=['created_by']),
            models.Index(fields=['last_edited_at']),
            GinIndex(fields=['tags']),
            GinIndex(fields=['properties']),
        ]
    
    def __str__(self):
        return self.title


class Block(MPTTModel, BaseModel):
    """
    Individual content block within a document.
    Uses MPTT (Modified Preorder Tree Traversal) for efficient hierarchical queries.
    
    Supports various block types similar to Notion:
    - text, heading1, heading2, heading3
    - todo, toggle, quote, callout
    - code, equation
    - image, file, video, embed
    - page (sub-page)
    - database (table, board, calendar views)
    """
    
    class BlockType(models.TextChoices):
        # Text blocks
        TEXT = 'text', 'Text'
        HEADING_1 = 'heading1', 'Heading 1'
        HEADING_2 = 'heading2', 'Heading 2'
        HEADING_3 = 'heading3', 'Heading 3'
        
        # List blocks
        BULLETED_LIST = 'bulleted_list', 'Bulleted List'
        NUMBERED_LIST = 'numbered_list', 'Numbered List'
        TODO = 'todo', 'To-do'
        TOGGLE = 'toggle', 'Toggle'
        
        # Content blocks
        QUOTE = 'quote', 'Quote'
        CALLOUT = 'callout', 'Callout'
        CODE = 'code', 'Code'
        EQUATION = 'equation', 'Equation'
        
        # Media blocks
        IMAGE = 'image', 'Image'
        VIDEO = 'video', 'Video'
        FILE = 'file', 'File'
        EMBED = 'embed', 'Embed'
        
        # Advanced blocks
        PAGE = 'page', 'Page'
        DATABASE = 'database', 'Database'
        DIVIDER = 'divider', 'Divider'
        TABLE_OF_CONTENTS = 'toc', 'Table of Contents'
    
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='blocks'
    )
    
    # MPTT fields for hierarchy
    parent = TreeForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children'
    )
    
    # Block type and content
    block_type = models.CharField(
        max_length=30,
        choices=BlockType.choices,
        default=BlockType.TEXT,
        db_index=True
    )
    
    # Rich text content stored as JSONB
    # Can be Prosemirror/Slate/Lexical JSON or plain text
    content = models.JSONField(
        default=dict,
        blank=True,
        help_text='Block content in structured format'
    )
    
    # Plain text for search
    text = models.TextField(
        blank=True,
        help_text='Plain text extraction for full-text search'
    )
    
    # Block-specific properties
    properties = models.JSONField(
        default=dict,
        blank=True,
        help_text='Block-specific settings (color, checked, language, etc.)'
    )
    
    # Ordering (within same parent and level)
    position = models.PositiveIntegerField(default=0, db_index=True)
    
    # Collaboration tracking
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_blocks'
    )
    last_edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='edited_blocks'
    )
    
    # Version for optimistic locking
    version = models.PositiveIntegerField(default=1)
    
    class MPTTMeta:
        order_insertion_by = ['position']
    
    class Meta:
        db_table = 'blocks'
        ordering = ['tree_id', 'lft', 'position']
        indexes = [
            models.Index(fields=['document', 'parent']),
            models.Index(fields=['block_type']),
            models.Index(fields=['position']),
            GinIndex(fields=['content']),
            GinIndex(fields=['properties']),
        ]
    
    def __str__(self):
        return f"{self.block_type} - {self.text[:50] if self.text else 'No content'}"


class DocumentVersion(BaseModel):
    """
    Store document versions for audit and restore functionality.
    """
    
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='versions'
    )
    version_number = models.PositiveIntegerField()
    
    # Snapshot of document state
    title = models.CharField(max_length=500)
    state = models.JSONField(default=dict)
    
    # Snapshot of all blocks as JSON
    blocks_snapshot = models.JSONField(default=list)
    
    # Who created this version
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    
    # Change metadata
    change_summary = models.TextField(blank=True)
    change_type = models.CharField(
        max_length=50,
        default='edit',
        help_text='manual_save, auto_save, restore, etc.'
    )
    
    # Size tracking
    content_size = models.PositiveIntegerField(
        default=0,
        help_text='Size in bytes'
    )
    
    class Meta:
        db_table = 'document_versions'
        ordering = ['-version_number']
        unique_together = ['document', 'version_number']
        indexes = [
            models.Index(fields=['document', '-version_number']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.document.title} v{self.version_number}"


class DocumentPermission(BaseModel):
    """
    Granular document-level permissions.
    Overrides workspace-level permissions.
    """
    
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='permissions'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='document_permissions'
    )
    role = models.CharField(
        max_length=20,
        choices=[
            ('owner', 'Owner'),
            ('editor', 'Editor'),
            ('commenter', 'Commenter'),
            ('viewer', 'Viewer'),
        ],
        default='viewer'
    )
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='granted_permissions'
    )
    
    class Meta:
        db_table = 'document_permissions'
        unique_together = ['document', 'user']
        indexes = [
            models.Index(fields=['document', 'role']),
            models.Index(fields=['user']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.document.title} ({self.role})"


class Comment(BaseModel, SoftDeleteModel):
    """
    Comments on documents or specific blocks.
    """
    
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='comments'
    )
    block = models.ForeignKey(
        Block,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='comments',
        help_text='Specific block this comment is attached to'
    )
    
    # Comment thread support
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='replies'
    )
    
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='comments'
    )
    
    # Comment content
    content = models.JSONField(
        help_text='Rich text content'
    )
    text = models.TextField(
        blank=True,
        help_text='Plain text for search'
    )
    
    # Resolution
    is_resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_comments'
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    # Mentions
    mentioned_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='mentioned_in_comments',
        blank=True
    )
    
    objects = SoftDeleteManager()
    
    class Meta:
        db_table = 'comments'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['document', 'is_resolved']),
            models.Index(fields=['block', 'parent']),
            models.Index(fields=['author', 'created_at']),
        ]
    
    def __str__(self):
        return f"Comment by {self.author.email} on {self.document.title}"


class Attachment(BaseModel):
    """
    File attachments for documents.
    """
    
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='attachments'
    )
    block = models.ForeignKey(
        Block,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='attachments'
    )
    
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    
    file = models.FileField(upload_to='attachments/%Y/%m/%d/')
    filename = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(help_text='Size in bytes')
    mime_type = models.CharField(max_length=100)
    
    # Optional metadata
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    duration = models.FloatField(null=True, blank=True, help_text='For videos/audio')
    
    class Meta:
        db_table = 'attachments'
        indexes = [
            models.Index(fields=['document']),
            models.Index(fields=['block']),
        ]
    
    def __str__(self):
        return self.filename
