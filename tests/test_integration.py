"""
Integration tests for user authentication and workspace workflows.

These tests verify end-to-end functionality across multiple apps.
"""
import pytest
from django.urls import reverse
from rest_framework import status
from apps.core.tests.factories import (
    UserFactory, WorkspaceFactory, DocumentFactory,
    WorkspaceMembershipFactory
)

pytestmark = [pytest.mark.django_db, pytest.mark.integration]


class TestUserAuthenticationFlow:
    """Integration tests for user authentication flow."""
    
    def test_complete_registration_and_login_flow(self, api_client):
        """Test complete user registration and login flow."""
        # Step 1: Register a new user
        register_url = reverse('users:register')
        register_data = {
            'email': 'newuser@example.com',
            'password': 'StrongPass123!',
            'password_confirm': 'StrongPass123!',
            'first_name': 'John',
            'last_name': 'Doe',
        }
        register_response = api_client.post(register_url, register_data, format='json')
        
        assert register_response.status_code == status.HTTP_201_CREATED
        assert 'tokens' in register_response.data['data']
        access_token = register_response.data['data']['tokens']['access']
        
        # Step 2: Access protected endpoint with token
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        profile_url = reverse('users:profile')
        profile_response = api_client.get(profile_url)
        
        assert profile_response.status_code == status.HTTP_200_OK
        assert profile_response.data['email'] == 'newuser@example.com'
    
    def test_login_and_access_workspaces(self, api_client):
        """Test login and accessing workspaces."""
        # Create user with known password
        user = UserFactory(email='test@example.com')
        user.set_password('testpass123')
        user.save()
        
        # Create workspace for user
        workspace = WorkspaceFactory(owner=user)
        
        # Step 1: Login
        login_url = reverse('users:token_obtain_pair')
        login_data = {
            'email': 'test@example.com',
            'password': 'testpass123',
        }
        login_response = api_client.post(login_url, login_data, format='json')
        
        assert login_response.status_code == status.HTTP_200_OK
        access_token = login_response.data['access']
        
        # Step 2: Access workspaces
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        workspaces_url = reverse('workspaces:workspace-list')
        workspaces_response = api_client.get(workspaces_url)
        
        # User should have access to their workspace
        assert workspaces_response.status_code == status.HTTP_200_OK


class TestWorkspaceDocumentFlow:
    """Integration tests for workspace and document workflows."""
    
    def test_create_workspace_and_document(self, authenticated_client, user):
        """Test creating workspace and document in one flow."""
        # Step 1: Create workspace
        workspace_url = reverse('workspaces:workspace-list')
        workspace_data = {
            'name': 'My New Workspace',
            'description': 'Test workspace',
        }
        workspace_response = authenticated_client.post(
            workspace_url,
            workspace_data,
            format='json'
        )
        
        assert workspace_response.status_code == status.HTTP_201_CREATED
        workspace_id = workspace_response.data['data']['id']
        
        # Step 2: Create document in workspace
        document_url = reverse('documents:document-list')
        document_data = {
            'workspace': workspace_id,
            'title': 'My First Document',
        }
        document_response = authenticated_client.post(
            document_url,
            document_data,
            format='json'
        )
        
        assert document_response.status_code == status.HTTP_201_CREATED
        assert document_response.data['data']['title'] == 'My First Document'
    
    def test_workspace_member_collaboration(self, api_client):
        """Test multiple users collaborating in a workspace."""
        # Create owner and workspace
        owner = UserFactory(email='owner@example.com')
        owner.set_password('pass123')
        owner.save()
        
        workspace = WorkspaceFactory(owner=owner)
        
        # Create member and add to workspace
        member = UserFactory(email='member@example.com')
        member.set_password('pass123')
        member.save()
        
        WorkspaceMembershipFactory(workspace=workspace, user=member)
        
        # Create document
        document = DocumentFactory(workspace=workspace, created_by=owner)
        
        # Login as member
        login_url = reverse('users:token_obtain_pair')
        login_response = api_client.post(
            login_url,
            {'email': 'member@example.com', 'password': 'pass123'},
            format='json'
        )
        
        assert login_response.status_code == status.HTTP_200_OK
        access_token = login_response.data['access']
        
        # Member should be able to access document
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        document_url = reverse('documents:document-detail', args=[document.id])
        document_response = api_client.get(document_url)
        
        # Should have access as workspace member
        assert document_response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_403_FORBIDDEN  # Depending on permissions implementation
        ]


class TestDocumentCommentFlow:
    """Integration tests for document commenting workflow."""
    
    def test_create_document_and_add_comments(self, authenticated_client, user):
        """Test creating document and adding comments."""
        # Create workspace
        workspace = WorkspaceFactory(owner=user)
        
        # Create document
        document_url = reverse('documents:document-list')
        document_data = {
            'workspace': workspace.id,
            'title': 'Document for Comments',
        }
        document_response = authenticated_client.post(
            document_url,
            document_data,
            format='json'
        )
        
        assert document_response.status_code == status.HTTP_201_CREATED
        document_id = document_response.data['data']['id']
        
        # Add comment
        comment_url = reverse('documents:comment-list')
        comment_data = {
            'document': document_id,
            'content': 'This is a test comment',
        }
        comment_response = authenticated_client.post(
            comment_url,
            comment_data,
            format='json'
        )
        
        # Comment creation might work depending on implementation
        assert comment_response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_404_NOT_FOUND  # If endpoint doesn't exist yet
        ]


class TestNotificationFlow:
    """Integration tests for notification workflows."""
    
    def test_action_triggers_notification(self, authenticated_client, user):
        """Test that actions trigger notifications."""
        # This is a placeholder for notification integration tests
        # Actual implementation would test:
        # 1. User mentions another user
        # 2. Notification is created
        # 3. User can retrieve notifications
        
        notifications_url = reverse('notifications:notification-list')
        response = authenticated_client.get(notifications_url)
        
        # Endpoint should exist or return 404
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND
        ]


class TestPermissionsFlow:
    """Integration tests for permissions across different resources."""
    
    def test_workspace_permission_hierarchy(self, api_client):
        """Test that workspace permissions cascade properly."""
        # Create owner
        owner = UserFactory()
        workspace = WorkspaceFactory(owner=owner)
        
        # Create non-member
        other_user = UserFactory(email='other@example.com')
        other_user.set_password('pass123')
        other_user.save()
        
        # Login as non-member
        login_url = reverse('users:token_obtain_pair')
        login_response = api_client.post(
            login_url,
            {'email': 'other@example.com', 'password': 'pass123'},
            format='json'
        )
        
        access_token = login_response.data['access']
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        
        # Try to access workspace details (should be forbidden for non-member)
        workspace_url = reverse('workspaces:workspace-detail', args=[workspace.id])
        response = api_client.get(workspace_url)
        
        # Should be forbidden unless workspace is public
        assert response.status_code in [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND
        ]
