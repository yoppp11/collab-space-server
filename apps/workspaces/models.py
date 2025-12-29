"""
Workspace Models with Granular RBAC Permissions

Implements Workspace -> Board/Folder -> Document hierarchy
with role-based access control at each level.
"""
from django.db import models
from django.conf import settings
from apps.core.models import BaseModel, SoftDeleteModel, SoftDeleteManager, OrderedModel


class WorkspaceRole(models.TextChoices):
    """Workspace-level roles."""
    OWNER = 'owner', 'Owner'
    ADMIN = 'admin', 'Admin'
    MEMBER = 'member', 'Member'
    GUEST = 'guest', 'Guest'


class DocumentRole(models.TextChoices):
    """Document-level roles (more granular)."""
    OWNER = 'owner', 'Owner'
    EDITOR = 'editor', 'Editor'
    COMMENTER = 'commenter', 'Commenter'
    VIEWER = 'viewer', 'Viewer'


class Workspace(BaseModel, SoftDeleteModel):
    """
    Top-level organizational unit.
    Workspaces contain boards/folders and documents.
    """
    
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True, db_index=True)
    description = models.TextField(blank=True)
    
    # Branding
    icon = models.CharField(max_length=50, blank=True, help_text='Emoji or icon name')
    icon_color = models.CharField(max_length=7, default='#6366f1')
    cover_image = models.ImageField(
        upload_to='workspace_covers/%Y/%m/',
        blank=True,
        null=True
    )
    
    # Owner (creator)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='owned_workspaces'
    )
    
    # Members through WorkspaceMembership
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='WorkspaceMembership',
        related_name='workspaces'
    )
    
    # Settings as JSONB
    settings = models.JSONField(
        default=dict,
        blank=True,
        help_text='Workspace settings and configuration'
    )
    
    # Visibility
    is_public = models.BooleanField(
        default=False,
        help_text='Public workspaces are visible to everyone'
    )
    
    objects = SoftDeleteManager()
    
    class Meta:
        db_table = 'workspaces'
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['owner']),
            models.Index(fields=['is_public']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return self.name
    
    def get_member_count(self):
        return self.memberships.filter(is_active=True).count()


class WorkspaceMembership(BaseModel):
    """
    Many-to-many relationship between Users and Workspaces
    with role information.
    """
    
    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name='memberships'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='workspace_memberships'
    )
    role = models.CharField(
        max_length=20,
        choices=WorkspaceRole.choices,
        default=WorkspaceRole.MEMBER
    )
    
    # Invitation tracking
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sent_workspace_invitations'
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'workspace_memberships'
        unique_together = ['workspace', 'user']
        indexes = [
            models.Index(fields=['workspace', 'role']),
            models.Index(fields=['user', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.workspace.name} ({self.role})"


class WorkspaceInvitation(BaseModel):
    """
    Pending invitations to workspaces.
    """
    
    class InvitationStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        ACCEPTED = 'accepted', 'Accepted'
        DECLINED = 'declined', 'Declined'
        EXPIRED = 'expired', 'Expired'
    
    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name='invitations'
    )
    email = models.EmailField()
    role = models.CharField(
        max_length=20,
        choices=WorkspaceRole.choices,
        default=WorkspaceRole.MEMBER
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='workspace_invitations'
    )
    status = models.CharField(
        max_length=20,
        choices=InvitationStatus.choices,
        default=InvitationStatus.PENDING
    )
    token = models.CharField(max_length=100, unique=True)
    expires_at = models.DateTimeField()
    message = models.TextField(blank=True)
    
    class Meta:
        db_table = 'workspace_invitations'
        indexes = [
            models.Index(fields=['email', 'status']),
            models.Index(fields=['token']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"Invitation to {self.email} for {self.workspace.name}"


class Board(BaseModel, SoftDeleteModel, OrderedModel):
    """
    Boards/Folders within a workspace.
    Can represent Trello-like boards or Notion-like folders.
    """
    
    class BoardType(models.TextChoices):
        BOARD = 'board', 'Board'  # Trello-like
        FOLDER = 'folder', 'Folder'  # Notion-like
        KANBAN = 'kanban', 'Kanban Board'
        CALENDAR = 'calendar', 'Calendar View'
        LIST = 'list', 'List View'
    
    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name='boards'
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    board_type = models.CharField(
        max_length=20,
        choices=BoardType.choices,
        default=BoardType.BOARD
    )
    
    # Visual customization
    icon = models.CharField(max_length=50, blank=True)
    color = models.CharField(max_length=7, default='#6366f1')
    cover_image = models.ImageField(
        upload_to='board_covers/%Y/%m/',
        blank=True,
        null=True
    )
    
    # Parent board for nested folders (Notion-style)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children'
    )
    
    # Board-specific settings
    settings = models.JSONField(default=dict, blank=True)
    
    # Visibility override
    is_private = models.BooleanField(
        default=False,
        help_text='Private boards are only visible to explicitly added members'
    )
    
    # Creator
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_boards'
    )
    
    objects = SoftDeleteManager()
    
    class Meta:
        db_table = 'boards'
        indexes = [
            models.Index(fields=['workspace', 'position']),
            models.Index(fields=['parent']),
            models.Index(fields=['board_type']),
        ]
    
    def __str__(self):
        return f"{self.workspace.name} / {self.name}"


class BoardMembership(BaseModel):
    """
    Board-level permissions for private boards.
    """
    
    board = models.ForeignKey(
        Board,
        on_delete=models.CASCADE,
        related_name='memberships'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='board_memberships'
    )
    role = models.CharField(
        max_length=20,
        choices=DocumentRole.choices,
        default=DocumentRole.EDITOR
    )
    
    class Meta:
        db_table = 'board_memberships'
        unique_together = ['board', 'user']
        indexes = [
            models.Index(fields=['board', 'role']),
        ]


class BoardList(BaseModel, OrderedModel):
    """
    Lists within a board (Trello columns).
    """
    
    board = models.ForeignKey(
        Board,
        on_delete=models.CASCADE,
        related_name='lists'
    )
    name = models.CharField(max_length=100)
    color = models.CharField(max_length=7, blank=True)
    
    # WIP limits for Kanban
    wip_limit = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Work in progress limit'
    )
    
    class Meta:
        db_table = 'board_lists'
        ordering = ['position']
        indexes = [
            models.Index(fields=['board', 'position']),
        ]
    
    def __str__(self):
        return f"{self.board.name} / {self.name}"
