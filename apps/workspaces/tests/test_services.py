"""
Tests for Workspace Services
"""
import pytest
from datetime import timedelta
from django.utils import timezone
from apps.workspaces.services import (
    WorkspaceService,
    BoardService,
    WorkspaceSelector,
)
from apps.workspaces.models import (
    Workspace,
    WorkspaceMembership,
    WorkspaceInvitation,
    Board,
    BoardList,
    WorkspaceRole,
)
from apps.core.tests.factories import (
    UserFactory,
    WorkspaceFactory,
    WorkspaceMembershipFactory,
    BoardFactory,
)


@pytest.mark.django_db
class TestWorkspaceService:
    """Test workspace service methods"""
    
    def test_create_workspace(self):
        """Test workspace creation with owner membership"""
        user = UserFactory()
        
        workspace = WorkspaceService.create_workspace(
            user=user,
            name='Test Workspace',
            description='Test description'
        )
        
        assert workspace.name == 'Test Workspace'
        assert workspace.owner == user
        assert workspace.slug == 'test-workspace'
        
        # Verify owner membership created
        membership = WorkspaceMembership.objects.get(
            workspace=workspace,
            user=user
        )
        assert membership.role == WorkspaceRole.OWNER
        
        # Verify default board created
        default_board = Board.objects.filter(
            workspace=workspace,
            name='General'
        ).first()
        assert default_board is not None
    
    def test_create_workspace_slug_collision(self):
        """Test workspace creation with duplicate names"""
        user = UserFactory()
        
        # Create first workspace
        workspace1 = WorkspaceService.create_workspace(
            user=user,
            name='My Workspace'
        )
        assert workspace1.slug == 'my-workspace'
        
        # Create second with same name
        workspace2 = WorkspaceService.create_workspace(
            user=user,
            name='My Workspace'
        )
        assert workspace2.slug == 'my-workspace-1'
    
    def test_invite_member_success(self):
        """Test inviting a new member"""
        workspace = WorkspaceFactory()
        inviter = UserFactory()
        
        invitation = WorkspaceService.invite_member(
            workspace=workspace,
            email='newuser@example.com',
            role=WorkspaceRole.MEMBER,
            invited_by=inviter,
            message='Welcome!'
        )
        
        assert invitation.email == 'newuser@example.com'
        assert invitation.role == WorkspaceRole.MEMBER
        assert invitation.status == WorkspaceInvitation.InvitationStatus.PENDING
        assert invitation.token is not None
        assert invitation.expires_at > timezone.now()
    
    def test_invite_member_already_member(self):
        """Test inviting an existing member fails"""
        workspace = WorkspaceFactory()
        user = UserFactory(email='existing@example.com')
        WorkspaceMembershipFactory(workspace=workspace, user=user)
        inviter = UserFactory()
        
        with pytest.raises(ValueError, match="already a member"):
            WorkspaceService.invite_member(
                workspace=workspace,
                email='existing@example.com',
                role=WorkspaceRole.MEMBER,
                invited_by=inviter
            )
    
    def test_invite_member_pending_invitation(self):
        """Test inviting when pending invitation exists"""
        workspace = WorkspaceFactory()
        inviter = UserFactory()
        
        # Create first invitation
        WorkspaceInvitation.objects.create(
            workspace=workspace,
            email='pending@example.com',
            role=WorkspaceRole.MEMBER,
            invited_by=inviter,
            token='token123',
            expires_at=timezone.now() + timedelta(days=7)
        )
        
        # Try to create another
        with pytest.raises(ValueError, match="already pending"):
            WorkspaceService.invite_member(
                workspace=workspace,
                email='pending@example.com',
                role=WorkspaceRole.MEMBER,
                invited_by=inviter
            )
    
    def test_accept_invitation_success(self):
        """Test accepting an invitation"""
        workspace = WorkspaceFactory()
        inviter = UserFactory()
        user = UserFactory()
        
        invitation = WorkspaceInvitation.objects.create(
            workspace=workspace,
            email=user.email,
            role=WorkspaceRole.MEMBER,
            invited_by=inviter,
            token='token123',
            expires_at=timezone.now() + timedelta(days=7)
        )
        
        membership = WorkspaceService.accept_invitation(invitation, user)
        
        assert membership.workspace == workspace
        assert membership.user == user
        assert membership.role == WorkspaceRole.MEMBER
        
        invitation.refresh_from_db()
        assert invitation.status == WorkspaceInvitation.InvitationStatus.ACCEPTED
    
    def test_accept_invitation_expired(self):
        """Test accepting expired invitation fails"""
        workspace = WorkspaceFactory()
        inviter = UserFactory()
        user = UserFactory()
        
        invitation = WorkspaceInvitation.objects.create(
            workspace=workspace,
            email=user.email,
            role=WorkspaceRole.MEMBER,
            invited_by=inviter,
            token='token123',
            expires_at=timezone.now() - timedelta(days=1)
        )
        
        with pytest.raises(ValueError, match="expired"):
            WorkspaceService.accept_invitation(invitation, user)
        
        # Note: The service updates status within the exception path
        # but doesn't commit because it raises before transaction commits
    
    def test_accept_invitation_already_accepted(self):
        """Test accepting already accepted invitation fails"""
        workspace = WorkspaceFactory()
        inviter = UserFactory()
        user = UserFactory()
        
        invitation = WorkspaceInvitation.objects.create(
            workspace=workspace,
            email=user.email,
            role=WorkspaceRole.MEMBER,
            invited_by=inviter,
            token='token123',
            expires_at=timezone.now() + timedelta(days=7),
            status=WorkspaceInvitation.InvitationStatus.ACCEPTED
        )
        
        with pytest.raises(ValueError, match="no longer valid"):
            WorkspaceService.accept_invitation(invitation, user)
    
    def test_update_member_role_success(self):
        """Test updating member role"""
        workspace = WorkspaceFactory()
        owner = workspace.owner
        WorkspaceMembershipFactory(workspace=workspace, user=owner, role=WorkspaceRole.OWNER)
        member = UserFactory()
        WorkspaceMembershipFactory(workspace=workspace, user=member, role=WorkspaceRole.MEMBER)
        
        updated_membership = WorkspaceService.update_member_role(
            workspace=workspace,
            user=member,
            new_role=WorkspaceRole.ADMIN,
            updated_by=owner
        )
        
        assert updated_membership.role == WorkspaceRole.ADMIN
    
    def test_update_member_role_cannot_change_owner(self):
        """Test cannot change owner's role"""
        workspace = WorkspaceFactory()
        owner = workspace.owner
        WorkspaceMembershipFactory(workspace=workspace, user=owner, role=WorkspaceRole.OWNER)
        admin = UserFactory()
        WorkspaceMembershipFactory(workspace=workspace, user=admin, role=WorkspaceRole.ADMIN)
        
        with pytest.raises(ValueError, match="Cannot change the owner"):
            WorkspaceService.update_member_role(
                workspace=workspace,
                user=owner,
                new_role=WorkspaceRole.MEMBER,
                updated_by=admin
            )
    
    def test_update_member_role_only_owner_can_promote_admin(self):
        """Test only owner can promote to admin"""
        workspace = WorkspaceFactory()
        admin = UserFactory()
        WorkspaceMembershipFactory(workspace=workspace, user=admin, role=WorkspaceRole.ADMIN)
        member = UserFactory()
        WorkspaceMembershipFactory(workspace=workspace, user=member, role=WorkspaceRole.MEMBER)
        
        with pytest.raises(ValueError, match="Only the owner can promote"):
            WorkspaceService.update_member_role(
                workspace=workspace,
                user=member,
                new_role=WorkspaceRole.ADMIN,
                updated_by=admin
            )
    
    def test_remove_member_success(self):
        """Test removing a member"""
        workspace = WorkspaceFactory()
        owner = workspace.owner
        WorkspaceMembershipFactory(workspace=workspace, user=owner, role=WorkspaceRole.OWNER)
        member = UserFactory()
        WorkspaceMembershipFactory(workspace=workspace, user=member, role=WorkspaceRole.MEMBER)
        
        result = WorkspaceService.remove_member(
            workspace=workspace,
            user=member,
            removed_by=owner
        )
        
        assert result is True
        assert not WorkspaceMembership.objects.filter(
            workspace=workspace,
            user=member
        ).exists()
    
    def test_remove_member_cannot_remove_owner(self):
        """Test cannot remove workspace owner"""
        workspace = WorkspaceFactory()
        owner = workspace.owner
        WorkspaceMembershipFactory(workspace=workspace, user=owner, role=WorkspaceRole.OWNER)
        
        with pytest.raises(ValueError, match="Cannot remove the workspace owner"):
            WorkspaceService.remove_member(
                workspace=workspace,
                user=owner,
                removed_by=owner
            )
    
    def test_remove_member_not_a_member(self):
        """Test removing non-member fails"""
        workspace = WorkspaceFactory()
        user = UserFactory()
        
        with pytest.raises(ValueError, match="not a member"):
            WorkspaceService.remove_member(
                workspace=workspace,
                user=user,
                removed_by=workspace.owner
            )
    
    def test_get_user_workspaces(self):
        """Test getting user's workspaces"""
        user = UserFactory()
        workspace1 = WorkspaceFactory()
        workspace2 = WorkspaceFactory()
        workspace3 = WorkspaceFactory()  # Not a member
        
        WorkspaceMembershipFactory(workspace=workspace1, user=user)
        WorkspaceMembershipFactory(workspace=workspace2, user=user)
        
        workspaces = WorkspaceService.get_user_workspaces(user)
        
        assert workspace1 in workspaces
        assert workspace2 in workspaces
        assert workspace3 not in workspaces


@pytest.mark.django_db
class TestBoardService:
    """Test board service methods"""
    
    def test_create_board_default(self):
        """Test creating a board with default lists"""
        workspace = WorkspaceFactory()
        user = UserFactory()
        
        board = BoardService.create_board(
            workspace=workspace,
            user=user,
            name='My Board',
            board_type=Board.BoardType.KANBAN
        )
        
        assert board.name == 'My Board'
        assert board.workspace == workspace
        assert board.created_by == user
        assert board.position == 1
        
        # Verify default lists created
        lists = BoardList.objects.filter(board=board).order_by('position')
        assert lists.count() == 3
        assert lists[0].name == 'To Do'
        assert lists[1].name == 'In Progress'
        assert lists[2].name == 'Done'
    
    def test_create_board_calendar_no_lists(self):
        """Test creating calendar board doesn't create lists"""
        workspace = WorkspaceFactory()
        user = UserFactory()
        
        board = BoardService.create_board(
            workspace=workspace,
            user=user,
            name='Calendar',
            board_type=Board.BoardType.CALENDAR
        )
        
        assert BoardList.objects.filter(board=board).count() == 0
    
    def test_create_board_with_parent(self):
        """Test creating nested board"""
        workspace = WorkspaceFactory()
        user = UserFactory()
        parent_board = BoardFactory(workspace=workspace)
        
        child_board = BoardService.create_board(
            workspace=workspace,
            user=user,
            name='Child Board',
            parent=parent_board
        )
        
        assert child_board.parent == parent_board
    
    def test_move_board_same_parent(self):
        """Test moving board within same parent"""
        workspace = WorkspaceFactory()
        board1 = BoardFactory(workspace=workspace, parent=None, position=0)
        board2 = BoardFactory(workspace=workspace, parent=None, position=1)
        board3 = BoardFactory(workspace=workspace, parent=None, position=2)
        
        # Move board3 to position 1
        BoardService.move_board(board3, new_position=1)
        
        board1.refresh_from_db()
        board2.refresh_from_db()
        board3.refresh_from_db()
        
        assert board1.position == 0
        assert board3.position == 1
        assert board2.position == 2
    
    def test_move_board_to_new_parent(self):
        """Test moving board to different parent"""
        workspace = WorkspaceFactory()
        parent1 = BoardFactory(workspace=workspace)
        parent2 = BoardFactory(workspace=workspace)
        
        board = BoardFactory(workspace=workspace, parent=parent1, position=0)
        
        BoardService.move_board(board, new_position=0, new_parent=parent2)
        
        board.refresh_from_db()
        assert board.parent == parent2
        assert board.position == 0


@pytest.mark.django_db
class TestWorkspaceSelector:
    """Test workspace selector methods"""
    
    def test_get_workspace_by_slug(self):
        """Test getting workspace by slug"""
        workspace = WorkspaceFactory(slug='my-workspace')
        
        found = WorkspaceSelector.get_workspace_by_slug('my-workspace')
        
        assert found == workspace
    
    def test_get_workspace_by_slug_not_found(self):
        """Test getting non-existent workspace returns None"""
        found = WorkspaceSelector.get_workspace_by_slug('nonexistent')
        
        assert found is None
    
    def test_get_workspace_members(self):
        """Test getting workspace members"""
        workspace = WorkspaceFactory()
        user1 = UserFactory()
        user2 = UserFactory()
        
        WorkspaceMembershipFactory(workspace=workspace, user=user1)
        WorkspaceMembershipFactory(workspace=workspace, user=user2)
        
        members = WorkspaceSelector.get_workspace_members(workspace)
        
        assert members.count() == 2
    
    def test_get_workspace_boards(self):
        """Test getting workspace boards"""
        workspace = WorkspaceFactory()
        board1 = BoardFactory(workspace=workspace, position=0)
        board2 = BoardFactory(workspace=workspace, position=1)
        
        boards = WorkspaceSelector.get_workspace_boards(workspace)
        
        assert list(boards) == [board1, board2]
    
    def test_get_board_with_lists(self):
        """Test getting board with prefetched lists"""
        board = BoardFactory()
        BoardList.objects.create(board=board, name='List 1', position=0)
        BoardList.objects.create(board=board, name='List 2', position=1)
        
        found = WorkspaceSelector.get_board_with_lists(str(board.id))
        
        assert found == board
        # Verify lists are prefetched (would need to check query count in real test)
        assert found.lists.count() == 2
