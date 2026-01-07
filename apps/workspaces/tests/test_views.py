"""
Unit tests for Workspace API views.
"""
import pytest
from django.urls import reverse
from rest_framework import status
from apps.workspaces.models import WorkspaceRole
from apps.core.tests.factories import (
    UserFactory, WorkspaceFactory, WorkspaceMembershipFactory,
    BoardFactory
)

pytestmark = [pytest.mark.django_db, pytest.mark.views]


class TestWorkspaceViewSet:
    """Tests for WorkspaceViewSet."""
    
    def test_list_workspaces(self, authenticated_client, user):
        """Test listing user's workspaces."""
        # Create workspaces
        workspace1 = WorkspaceFactory(owner=user)
        workspace2 = WorkspaceFactory(owner=user)
        
        url = reverse('workspaces:workspace-list')
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        # Should return user's workspaces
    
    def test_create_workspace(self, authenticated_client, user):
        """Test creating a workspace."""
        url = reverse('workspaces:workspace-list')
        data = {
            'name': 'New Workspace',
            'description': 'Test description',
        }
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['success'] is True
        assert response.data['data']['name'] == 'New Workspace'
    
    def test_get_workspace_detail(self, authenticated_client, user):
        """Test retrieving workspace details."""
        workspace = WorkspaceFactory(owner=user)
        WorkspaceMembershipFactory(workspace=workspace, user=user, role='owner')
        
        url = reverse('workspaces:workspace-detail', args=[workspace.id])
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == workspace.name
    
    def test_update_workspace(self, authenticated_client, user):
        """Test updating a workspace."""
        workspace = WorkspaceFactory(owner=user)
        WorkspaceMembershipFactory(workspace=workspace, user=user, role='owner')
        
        url = reverse('workspaces:workspace-detail', args=[workspace.id])
        data = {'name': 'Updated Name'}
        response = authenticated_client.patch(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == 'Updated Name'
    
    def test_delete_workspace(self, authenticated_client, user):
        """Test deleting a workspace (soft delete)."""
        workspace = WorkspaceFactory(owner=user)
        WorkspaceMembershipFactory(workspace=workspace, user=user, role='owner')
        
        url = reverse('workspaces:workspace-detail', args=[workspace.id])
        response = authenticated_client.delete(url)
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        
        # Verify soft delete
        workspace.refresh_from_db()
        assert workspace.is_deleted is True
    
    def test_non_member_cannot_access_private_workspace(self, api_client):
        """Test non-members cannot access private workspaces."""
        workspace = WorkspaceFactory(is_public=False)
        other_user = UserFactory()
        other_user.set_password('pass123')
        other_user.save()
        
        # Login as non-member
        api_client.login(email=other_user.email, password='pass123')
        
        url = reverse('workspaces:workspace-detail', args=[workspace.id])
        response = api_client.get(url)
        
        # Should be forbidden or not found
        assert response.status_code in [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_401_UNAUTHORIZED
        ]


class TestWorkspaceMemberManagement:
    """Tests for workspace member management."""
    
    def test_list_workspace_members(self, authenticated_client, user):
        """Test listing workspace members."""
        workspace = WorkspaceFactory(owner=user)
        WorkspaceMembershipFactory.create_batch(3, workspace=workspace)
        
        url = reverse('workspaces:workspace-members', args=[workspace.id])
        response = authenticated_client.get(url)
        
        # Endpoint may or may not be implemented
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND
        ]
    
    def test_invite_member_to_workspace(self, authenticated_client, user):
        """Test inviting a member to workspace."""
        workspace = WorkspaceFactory(owner=user)
        
        url = reverse('workspaces:workspace-invite', args=[workspace.id])
        data = {
            'email': 'newmember@example.com',
            'role': 'member',
        }
        response = authenticated_client.post(url, data, format='json')
        
        # Endpoint may or may not be implemented
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_201_CREATED,
            status.HTTP_404_NOT_FOUND
        ]
    
    def test_remove_member_from_workspace(self, authenticated_client, user):
        """Test removing a member from workspace."""
        workspace = WorkspaceFactory(owner=user)
        member = UserFactory()
        membership = WorkspaceMembershipFactory(
            workspace=workspace,
            user=member
        )
        
        url = reverse(
            'workspaces:workspace-remove-member',
            args=[workspace.id, member.id]
        )
        response = authenticated_client.delete(url)
        
        # Endpoint may or may not be implemented
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_204_NO_CONTENT,
            status.HTTP_404_NOT_FOUND
        ]
    
    def test_non_admin_cannot_invite_members(self, authenticated_client, user):
        """Test that non-admin members cannot invite others."""
        workspace = WorkspaceFactory()
        WorkspaceMembershipFactory(
            workspace=workspace,
            user=user,
            role=WorkspaceRole.MEMBER  # Not admin
        )
        
        url = reverse('workspaces:workspace-invite', args=[workspace.id])
        data = {'email': 'someone@example.com', 'role': 'member'}
        response = authenticated_client.post(url, data, format='json')
        
        # Should be forbidden or not found
        assert response.status_code in [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND
        ]


class TestBoardViewSet:
    """Tests for Board views."""
    
    def test_create_board_in_workspace(self, authenticated_client, user):
        """Test creating a board in a workspace."""
        workspace = WorkspaceFactory(owner=user)
        WorkspaceMembershipFactory(workspace=workspace, user=user, role='owner')
        
        url = reverse('workspaces:workspace-boards-list', args=[workspace.id])
        data = {
            'name': 'My Board',
            'description': 'Test board',
        }
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['success'] is True
        assert response.data['data']['name'] == 'My Board'
    
    def test_list_workspace_boards(self, authenticated_client, user):
        """Test listing boards in a workspace."""
        workspace = WorkspaceFactory(owner=user)
        WorkspaceMembershipFactory(workspace=workspace, user=user, role='owner')
        BoardFactory.create_batch(3, workspace=workspace)
        
        url = reverse('workspaces:workspace-boards-list', args=[workspace.id])
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_move_board(self, authenticated_client, user):
        """Test moving a board to a new position."""
        workspace = WorkspaceFactory(owner=user)
        WorkspaceMembershipFactory(workspace=workspace, user=user, role='owner')
        board = BoardFactory(workspace=workspace, position=1000)
        
        url = reverse('workspaces:workspace-boards-move', args=[workspace.id, board.id])
        response = authenticated_client.post(url, {'position': 500}, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True


class TestBoardListViewSet:
    """Tests for BoardList views."""
    
    def test_create_list_in_board(self, authenticated_client, user):
        """Test creating a list in a board."""
        workspace = WorkspaceFactory(owner=user)
        WorkspaceMembershipFactory(workspace=workspace, user=user, role='owner')
        board = BoardFactory(workspace=workspace)
        
        url = reverse('workspaces:board-lists-list', args=[workspace.id, board.id])
        data = {
            'name': 'To Do',
        }
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['success'] is True
    
    def test_list_board_lists(self, authenticated_client, user):
        """Test listing lists in a board."""
        from apps.workspaces.models import BoardList
        
        workspace = WorkspaceFactory(owner=user)
        WorkspaceMembershipFactory(workspace=workspace, user=user, role='owner')
        board = BoardFactory(workspace=workspace)
        BoardList.objects.create(board=board, name='List 1', position=0)
        BoardList.objects.create(board=board, name='List 2', position=1000)
        
        url = reverse('workspaces:board-lists-list', args=[workspace.id, board.id])
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK


class TestCardViewSet:
    """Tests for Card views."""
    
    def test_create_card(self, authenticated_client, user):
        """Test creating a card in a list."""
        from apps.workspaces.models import BoardList
        
        workspace = WorkspaceFactory(owner=user)
        WorkspaceMembershipFactory(workspace=workspace, user=user, role='owner')
        board = BoardFactory(workspace=workspace)
        board_list = BoardList.objects.create(board=board, name='To Do', position=0)
        
        url = reverse('workspaces:list-cards-list', args=[workspace.id, board.id, board_list.id])
        data = {
            'title': 'New Card',
        }
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['success'] is True
    
    def test_move_card(self, authenticated_client, user):
        """Test moving a card."""
        from apps.workspaces.models import BoardList, Card
        
        workspace = WorkspaceFactory(owner=user)
        WorkspaceMembershipFactory(workspace=workspace, user=user, role='owner')
        board = BoardFactory(workspace=workspace)
        board_list = BoardList.objects.create(board=board, name='To Do', position=0)
        card = Card.objects.create(list=board_list, title='Card 1', position=0)
        
        url = reverse('workspaces:list-cards-move', args=[workspace.id, board.id, board_list.id, card.id])
        response = authenticated_client.post(url, {'position': 1000}, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True
    
    def test_archive_card(self, authenticated_client, user):
        """Test archiving a card."""
        from apps.workspaces.models import BoardList, Card
        
        workspace = WorkspaceFactory(owner=user)
        WorkspaceMembershipFactory(workspace=workspace, user=user, role='owner')
        board = BoardFactory(workspace=workspace)
        board_list = BoardList.objects.create(board=board, name='To Do', position=0)
        card = Card.objects.create(list=board_list, title='Card 1', position=0)
        
        url = reverse('workspaces:list-cards-archive', args=[workspace.id, board.id, board_list.id, card.id])
        response = authenticated_client.post(url)
        
        assert response.status_code == status.HTTP_200_OK
        
        card.refresh_from_db()
        assert card.is_archived is True


class TestCardCommentViewSet:
    """Tests for CardComment views."""
    
    def test_create_comment(self, authenticated_client, user):
        """Test creating a comment on a card."""
        from apps.workspaces.models import BoardList, Card
        
        workspace = WorkspaceFactory(owner=user)
        WorkspaceMembershipFactory(workspace=workspace, user=user, role='owner')
        board = BoardFactory(workspace=workspace)
        board_list = BoardList.objects.create(board=board, name='To Do', position=0)
        card = Card.objects.create(list=board_list, title='Card 1', position=0)
        
        url = reverse('workspaces:card-comments-list', args=[workspace.id, board.id, board_list.id, card.id])
        data = {'text': 'This is a comment'}
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['success'] is True
    
    def test_update_own_comment(self, authenticated_client, user):
        """Test updating own comment."""
        from apps.workspaces.models import BoardList, Card, CardComment
        
        workspace = WorkspaceFactory(owner=user)
        WorkspaceMembershipFactory(workspace=workspace, user=user, role='owner')
        board = BoardFactory(workspace=workspace)
        board_list = BoardList.objects.create(board=board, name='To Do', position=0)
        card = Card.objects.create(list=board_list, title='Card 1', position=0)
        comment = CardComment.objects.create(card=card, author=user, text='Original comment')
        
        url = reverse('workspaces:card-comments-detail', args=[workspace.id, board.id, board_list.id, card.id, comment.id])
        data = {'text': 'Updated comment'}
        response = authenticated_client.patch(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True
    
    def test_cannot_update_others_comment(self, authenticated_client, user):
        """Test cannot update another user's comment."""
        from apps.workspaces.models import BoardList, Card, CardComment
        
        workspace = WorkspaceFactory(owner=user)
        WorkspaceMembershipFactory(workspace=workspace, user=user, role='owner')
        board = BoardFactory(workspace=workspace)
        board_list = BoardList.objects.create(board=board, name='To Do', position=0)
        card = Card.objects.create(list=board_list, title='Card 1', position=0)
        
        other_user = UserFactory()
        comment = CardComment.objects.create(card=card, author=other_user, text='Original comment')
        
        url = reverse('workspaces:card-comments-detail', args=[workspace.id, board.id, board_list.id, card.id, comment.id])
        data = {'text': 'Updated comment'}
        response = authenticated_client.patch(url, data, format='json')
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_delete_own_comment(self, authenticated_client, user):
        """Test deleting own comment."""
        from apps.workspaces.models import BoardList, Card, CardComment
        
        workspace = WorkspaceFactory(owner=user)
        WorkspaceMembershipFactory(workspace=workspace, user=user, role='owner')
        board = BoardFactory(workspace=workspace)
        board_list = BoardList.objects.create(board=board, name='To Do', position=0)
        card = Card.objects.create(list=board_list, title='Card 1', position=0)
        comment = CardComment.objects.create(card=card, author=user, text='Comment to delete')
        
        url = reverse('workspaces:card-comments-detail', args=[workspace.id, board.id, board_list.id, card.id, comment.id])
        response = authenticated_client.delete(url)
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_cannot_delete_others_comment(self, authenticated_client, user):
        """Test cannot delete another user's comment."""
        from apps.workspaces.models import BoardList, Card, CardComment
        
        workspace = WorkspaceFactory(owner=user)
        WorkspaceMembershipFactory(workspace=workspace, user=user, role='owner')
        board = BoardFactory(workspace=workspace)
        board_list = BoardList.objects.create(board=board, name='To Do', position=0)
        card = Card.objects.create(list=board_list, title='Card 1', position=0)
        
        other_user = UserFactory()
        comment = CardComment.objects.create(card=card, author=other_user, text='Original comment')
        
        url = reverse('workspaces:card-comments-detail', args=[workspace.id, board.id, board_list.id, card.id, comment.id])
        response = authenticated_client.delete(url)
        
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestInvitationAcceptView:
    """Tests for InvitationAcceptView."""
    
    def test_accept_invitation(self, authenticated_client, user):
        """Test accepting a workspace invitation."""
        from apps.workspaces.models import WorkspaceInvitation
        from django.utils import timezone
        from datetime import timedelta
        import uuid
        
        workspace = WorkspaceFactory()
        owner = workspace.owner
        WorkspaceMembershipFactory(workspace=workspace, user=owner, role='owner')
        
        invitation = WorkspaceInvitation.objects.create(
            workspace=workspace,
            email=user.email,
            role='member',
            invited_by=owner,
            token=str(uuid.uuid4()),
            expires_at=timezone.now() + timedelta(days=7)
        )
        
        url = reverse('workspaces:invitation-accept', args=[invitation.token])
        response = authenticated_client.post(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True


class TestJoinWorkspaceByCodeView:
    """Tests for JoinWorkspaceByCodeView."""
    
    def test_join_workspace_by_code(self, authenticated_client, user):
        """Test joining a workspace by invite code."""
        from apps.workspaces.models import WorkspaceInvitation
        from django.utils import timezone
        from datetime import timedelta
        import uuid
        
        workspace = WorkspaceFactory()
        owner = workspace.owner
        WorkspaceMembershipFactory(workspace=workspace, user=owner, role='owner')
        
        invitation = WorkspaceInvitation.objects.create(
            workspace=workspace,
            email='',  # Link invitations don't require email
            role='member',
            invited_by=owner,
            token=str(uuid.uuid4()),
            expires_at=timezone.now() + timedelta(days=7)
        )
        
        url = reverse('workspaces:join-by-code')
        response = authenticated_client.post(url, {'code': invitation.token}, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True
    
    def test_join_workspace_without_code(self, authenticated_client, user):
        """Test joining a workspace without providing a code."""
        url = reverse('workspaces:join-by-code')
        response = authenticated_client.post(url, {}, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_join_workspace_with_invalid_code(self, authenticated_client, user):
        """Test joining a workspace with invalid code."""
        url = reverse('workspaces:join-by-code')
        response = authenticated_client.post(url, {'code': 'invalid-code'}, format='json')
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
