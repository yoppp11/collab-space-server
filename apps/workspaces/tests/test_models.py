"""
Unit tests for Workspace models.
"""
import pytest
from django.db import IntegrityError
from django.utils import timezone
from datetime import timedelta
from apps.workspaces.models import (
    Workspace, WorkspaceMembership, WorkspaceInvitation,
    Board, BoardMembership, BoardList, WorkspaceRole
)
from apps.core.tests.factories import (
    UserFactory, WorkspaceFactory, WorkspaceMembershipFactory,
    BoardFactory
)

pytestmark = pytest.mark.django_db


class TestWorkspaceModel:
    """Tests for the Workspace model."""
    
    def test_create_workspace(self, user):
        """Test creating a workspace."""
        workspace = WorkspaceFactory(
            name='Test Workspace',
            owner=user
        )
        assert workspace.name == 'Test Workspace'
        assert workspace.owner == user
        assert workspace.is_public is False
    
    def test_workspace_str_representation(self):
        """Test workspace string representation."""
        workspace = WorkspaceFactory(name='My Workspace')
        assert str(workspace) == 'My Workspace'
    
    def test_workspace_slug_must_be_unique(self):
        """Test that workspace slug must be unique."""
        WorkspaceFactory(slug='test-workspace')
        with pytest.raises(IntegrityError):
            WorkspaceFactory(slug='test-workspace')
    
    def test_workspace_settings_default(self):
        """Test workspace settings are initialized with defaults."""
        workspace = WorkspaceFactory()
        assert workspace.settings is not None
        assert 'allow_guests' in workspace.settings
        assert workspace.settings['allow_guests'] is True
    
    def test_get_member_count(self, workspace_with_members):
        """Test getting workspace member count."""
        count = workspace_with_members.get_member_count()
        assert count == 3
    
    def test_workspace_soft_delete(self, workspace):
        """Test soft deleting a workspace."""
        workspace.delete()
        assert workspace.is_deleted is True
        assert workspace.deleted_at is not None


class TestWorkspaceMembershipModel:
    """Tests for the WorkspaceMembership model."""
    
    def test_create_membership(self, workspace, user):
        """Test creating a workspace membership."""
        membership = WorkspaceMembershipFactory(
            workspace=workspace,
            user=user,
            role=WorkspaceRole.MEMBER
        )
        assert membership.workspace == workspace
        assert membership.user == user
        assert membership.role == WorkspaceRole.MEMBER
        assert membership.is_active is True
    
    def test_membership_str_representation(self, workspace, user):
        """Test membership string representation."""
        membership = WorkspaceMembershipFactory(
            workspace=workspace,
            user=user,
            role=WorkspaceRole.ADMIN
        )
        assert user.email in str(membership)
        assert workspace.name in str(membership)
        assert 'admin' in str(membership)
    
    def test_unique_workspace_user_pair(self, workspace, user):
        """Test that workspace-user pair must be unique."""
        WorkspaceMembershipFactory(workspace=workspace, user=user)
        with pytest.raises(IntegrityError):
            WorkspaceMembershipFactory(workspace=workspace, user=user)
    
    def test_user_can_join_multiple_workspaces(self, user):
        """Test that a user can join multiple workspaces."""
        workspace1 = WorkspaceFactory()
        workspace2 = WorkspaceFactory()
        
        membership1 = WorkspaceMembershipFactory(workspace=workspace1, user=user)
        membership2 = WorkspaceMembershipFactory(workspace=workspace2, user=user)
        
        assert membership1.workspace != membership2.workspace
        assert user.workspace_memberships.count() == 2
    
    def test_membership_roles(self, workspace, user):
        """Test different membership roles."""
        for role, _ in WorkspaceRole.choices:
            membership = WorkspaceMembershipFactory(
                workspace=workspace,
                user=UserFactory(),
                role=role
            )
            assert membership.role == role


class TestWorkspaceInvitationModel:
    """Tests for the WorkspaceInvitation model."""
    
    def test_create_invitation(self, workspace, user):
        """Test creating a workspace invitation."""
        expires_at = timezone.now() + timedelta(days=7)
        invitation = WorkspaceInvitation.objects.create(
            workspace=workspace,
            email='invitee@example.com',
            role=WorkspaceRole.MEMBER,
            invited_by=user,
            token='test-token-123',
            expires_at=expires_at
        )
        
        assert invitation.workspace == workspace
        assert invitation.email == 'invitee@example.com'
        assert invitation.status == WorkspaceInvitation.InvitationStatus.PENDING
    
    def test_invitation_str_representation(self, workspace, user):
        """Test invitation string representation."""
        invitation = WorkspaceInvitation.objects.create(
            workspace=workspace,
            email='test@example.com',
            invited_by=user,
            token='token123',
            expires_at=timezone.now() + timedelta(days=7)
        )
        assert 'test@example.com' in str(invitation)
        assert workspace.name in str(invitation)
    
    def test_invitation_token_unique(self, workspace, user):
        """Test that invitation token must be unique."""
        expires_at = timezone.now() + timedelta(days=7)
        WorkspaceInvitation.objects.create(
            workspace=workspace,
            email='user1@example.com',
            invited_by=user,
            token='unique-token',
            expires_at=expires_at
        )
        
        with pytest.raises(IntegrityError):
            WorkspaceInvitation.objects.create(
                workspace=workspace,
                email='user2@example.com',
                invited_by=user,
                token='unique-token',  # Same token
                expires_at=expires_at
            )


class TestBoardModel:
    """Tests for the Board model."""
    
    def test_create_board(self, workspace, user):
        """Test creating a board."""
        board = BoardFactory(
            workspace=workspace,
            name='My Board',
            created_by=user
        )
        assert board.name == 'My Board'
        assert board.workspace == workspace
        assert board.created_by == user
    
    def test_board_str_representation(self, workspace):
        """Test board string representation."""
        board = BoardFactory(workspace=workspace, name='Test Board')
        assert workspace.name in str(board)
        assert 'Test Board' in str(board)
    
    def test_board_types(self, workspace):
        """Test different board types."""
        for board_type, _ in Board.BoardType.choices:
            board = BoardFactory(workspace=workspace, board_type=board_type)
            assert board.board_type == board_type
    
    def test_nested_boards(self, workspace):
        """Test creating nested boards (folders)."""
        parent = BoardFactory(workspace=workspace, board_type=Board.BoardType.FOLDER)
        child = BoardFactory(
            workspace=workspace,
            parent=parent,
            board_type=Board.BoardType.FOLDER
        )
        
        assert child.parent == parent
        assert child in parent.children.all()
    
    def test_board_settings_default(self, workspace):
        """Test board settings default to empty dict."""
        board = BoardFactory(workspace=workspace)
        assert board.settings == {}
    
    def test_board_soft_delete(self, board):
        """Test soft deleting a board."""
        board.delete()
        assert board.is_deleted is True


class TestBoardMembershipModel:
    """Tests for the BoardMembership model."""
    
    def test_create_board_membership(self, board, user):
        """Test creating a board membership."""
        membership = BoardMembership.objects.create(
            board=board,
            user=user,
            role='editor'
        )
        
        assert membership.board == board
        assert membership.user == user
        assert membership.role == 'editor'
    
    def test_unique_board_user_pair(self, board, user):
        """Test that board-user pair must be unique."""
        BoardMembership.objects.create(board=board, user=user)
        with pytest.raises(IntegrityError):
            BoardMembership.objects.create(board=board, user=user)


class TestBoardListModel:
    """Tests for the BoardList model."""
    
    def test_create_board_list(self, board):
        """Test creating a board list."""
        board_list = BoardList.objects.create(
            board=board,
            name='To Do',
            position=1000
        )
        
        assert board_list.board == board
        assert board_list.name == 'To Do'
        assert board_list.position == 1000
    
    def test_board_list_str_representation(self, board):
        """Test board list string representation."""
        board_list = BoardList.objects.create(
            board=board,
            name='In Progress'
        )
        assert board.name in str(board_list)
        assert 'In Progress' in str(board_list)
    
    def test_board_list_ordering(self, board):
        """Test that board lists are ordered by position."""
        list1 = BoardList.objects.create(board=board, name='List 1', position=3000)
        list2 = BoardList.objects.create(board=board, name='List 2', position=1000)
        list3 = BoardList.objects.create(board=board, name='List 3', position=2000)
        
        lists = list(board.lists.all())
        assert lists[0] == list2  # position 1000
        assert lists[1] == list3  # position 2000
        assert lists[2] == list1  # position 3000
    
    def test_wip_limit(self, board):
        """Test setting WIP limit on board list."""
        board_list = BoardList.objects.create(
            board=board,
            name='In Progress',
            wip_limit=5
        )
        assert board_list.wip_limit == 5
