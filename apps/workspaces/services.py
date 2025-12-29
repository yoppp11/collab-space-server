"""
Workspace Services - Business Logic Layer
"""
from typing import Optional, List
from django.db import transaction
from django.utils import timezone
from django.core.cache import cache
import secrets

from .models import (
    Workspace, WorkspaceMembership, WorkspaceInvitation,
    Board, BoardMembership, BoardList, WorkspaceRole
)
from .permissions import invalidate_permission_cache


class WorkspaceService:
    """
    Service class for workspace-related business logic.
    """
    
    @staticmethod
    @transaction.atomic
    def create_workspace(user, name: str, **kwargs) -> Workspace:
        """
        Create a new workspace with the user as owner.
        """
        from django.utils.text import slugify
        
        base_slug = slugify(name)
        slug = base_slug
        counter = 1
        while Workspace.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        
        workspace = Workspace.objects.create(
            name=name,
            slug=slug,
            owner=user,
            **kwargs
        )
        
        # Add creator as owner
        WorkspaceMembership.objects.create(
            workspace=workspace,
            user=user,
            role=WorkspaceRole.OWNER
        )
        
        # Create default board
        Board.objects.create(
            workspace=workspace,
            name='General',
            board_type=Board.BoardType.BOARD,
            created_by=user,
            position=0
        )
        
        return workspace
    
    @staticmethod
    @transaction.atomic
    def invite_member(
        workspace: Workspace,
        email: str,
        role: str,
        invited_by,
        message: str = ''
    ) -> WorkspaceInvitation:
        """
        Create an invitation for a new member.
        """
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Check if user already exists and is a member
        existing_user = User.objects.filter(email__iexact=email).first()
        if existing_user:
            existing_membership = WorkspaceMembership.objects.filter(
                workspace=workspace,
                user=existing_user
            ).first()
            if existing_membership:
                raise ValueError("User is already a member of this workspace")
        
        # Check for pending invitation
        pending = WorkspaceInvitation.objects.filter(
            workspace=workspace,
            email__iexact=email,
            status=WorkspaceInvitation.InvitationStatus.PENDING
        ).first()
        if pending:
            raise ValueError("An invitation is already pending for this email")
        
        # Create invitation
        invitation = WorkspaceInvitation.objects.create(
            workspace=workspace,
            email=email,
            role=role,
            invited_by=invited_by,
            message=message,
            token=secrets.token_urlsafe(32),
            expires_at=timezone.now() + timezone.timedelta(days=7)
        )
        
        return invitation
    
    @staticmethod
    @transaction.atomic
    def accept_invitation(invitation: WorkspaceInvitation, user) -> WorkspaceMembership:
        """
        Accept a workspace invitation.
        """
        if invitation.status != WorkspaceInvitation.InvitationStatus.PENDING:
            raise ValueError("Invitation is no longer valid")
        
        if invitation.expires_at < timezone.now():
            invitation.status = WorkspaceInvitation.InvitationStatus.EXPIRED
            invitation.save()
            raise ValueError("Invitation has expired")
        
        # Create membership
        membership = WorkspaceMembership.objects.create(
            workspace=invitation.workspace,
            user=user,
            role=invitation.role,
            invited_by=invitation.invited_by
        )
        
        # Update invitation status
        invitation.status = WorkspaceInvitation.InvitationStatus.ACCEPTED
        invitation.save()
        
        return membership
    
    @staticmethod
    @transaction.atomic
    def update_member_role(
        workspace: Workspace,
        user,
        new_role: str,
        updated_by
    ) -> WorkspaceMembership:
        """
        Update a member's role in a workspace.
        """
        membership = WorkspaceMembership.objects.get(
            workspace=workspace,
            user=user
        )
        
        # Cannot change owner's role
        if membership.role == WorkspaceRole.OWNER:
            raise ValueError("Cannot change the owner's role")
        
        # Only owner can make someone admin
        updater_role = WorkspaceMembership.objects.get(
            workspace=workspace,
            user=updated_by
        ).role
        
        if new_role == WorkspaceRole.ADMIN and updater_role != WorkspaceRole.OWNER:
            raise ValueError("Only the owner can promote members to admin")
        
        membership.role = new_role
        membership.save()
        
        # Invalidate permission cache
        invalidate_permission_cache(user.id, workspace_id=workspace.id)
        
        return membership
    
    @staticmethod
    @transaction.atomic
    def remove_member(workspace: Workspace, user, removed_by) -> bool:
        """
        Remove a member from a workspace.
        """
        membership = WorkspaceMembership.objects.filter(
            workspace=workspace,
            user=user
        ).first()
        
        if not membership:
            raise ValueError("User is not a member of this workspace")
        
        if membership.role == WorkspaceRole.OWNER:
            raise ValueError("Cannot remove the workspace owner")
        
        membership.delete()
        
        # Invalidate permission cache
        invalidate_permission_cache(user.id, workspace_id=workspace.id)
        
        return True
    
    @staticmethod
    def get_user_workspaces(user) -> List[Workspace]:
        """
        Get all workspaces a user is a member of.
        """
        return Workspace.objects.filter(
            memberships__user=user,
            memberships__is_active=True,
            is_deleted=False
        ).distinct().order_by('-updated_at')


class BoardService:
    """
    Service class for board-related business logic.
    """
    
    @staticmethod
    @transaction.atomic
    def create_board(
        workspace: Workspace,
        user,
        name: str,
        board_type: str = Board.BoardType.BOARD,
        **kwargs
    ) -> Board:
        """
        Create a new board in a workspace.
        """
        from django.db.models import Max
        
        parent = kwargs.get('parent')
        max_position = Board.objects.filter(
            workspace=workspace,
            parent=parent
        ).aggregate(max_pos=Max('position'))['max_pos'] or 0
        
        board = Board.objects.create(
            workspace=workspace,
            name=name,
            board_type=board_type,
            created_by=user,
            position=max_position + 1,
            **kwargs
        )
        
        # Create default lists for Kanban boards
        if board_type in [Board.BoardType.KANBAN, Board.BoardType.BOARD]:
            default_lists = ['To Do', 'In Progress', 'Done']
            for i, list_name in enumerate(default_lists):
                BoardList.objects.create(
                    board=board,
                    name=list_name,
                    position=i
                )
        
        return board
    
    @staticmethod
    @transaction.atomic
    def move_board(board: Board, new_position: int, new_parent: Optional[Board] = None):
        """
        Move a board to a new position or parent.
        """
        from django.db.models import F
        
        old_position = board.position
        old_parent = board.parent
        
        # If parent is changing
        if new_parent != old_parent:
            # Update positions in old parent's children
            Board.objects.filter(
                workspace=board.workspace,
                parent=old_parent,
                position__gt=old_position
            ).update(position=F('position') - 1)
            
            # Update positions in new parent's children
            Board.objects.filter(
                workspace=board.workspace,
                parent=new_parent,
                position__gte=new_position
            ).update(position=F('position') + 1)
            
            board.parent = new_parent
        else:
            # Same parent, just reorder
            if new_position > old_position:
                Board.objects.filter(
                    workspace=board.workspace,
                    parent=old_parent,
                    position__gt=old_position,
                    position__lte=new_position
                ).update(position=F('position') - 1)
            else:
                Board.objects.filter(
                    workspace=board.workspace,
                    parent=old_parent,
                    position__lt=old_position,
                    position__gte=new_position
                ).update(position=F('position') + 1)
        
        board.position = new_position
        board.save()


class WorkspaceSelector:
    """
    Selector class for workspace queries.
    """
    
    @staticmethod
    def get_workspace_by_slug(slug: str) -> Optional[Workspace]:
        """Get workspace by slug."""
        return Workspace.objects.filter(slug=slug, is_deleted=False).first()
    
    @staticmethod
    def get_workspace_members(workspace: Workspace):
        """Get all active members of a workspace."""
        return WorkspaceMembership.objects.filter(
            workspace=workspace,
            is_active=True
        ).select_related('user', 'invited_by')
    
    @staticmethod
    def get_workspace_boards(workspace: Workspace, parent: Optional[Board] = None):
        """Get boards in a workspace."""
        return Board.objects.filter(
            workspace=workspace,
            parent=parent,
            is_deleted=False
        ).order_by('position')
    
    @staticmethod
    def get_board_with_lists(board_id: str) -> Optional[Board]:
        """Get board with prefetched lists."""
        return Board.objects.filter(
            id=board_id,
            is_deleted=False
        ).prefetch_related('lists').first()
