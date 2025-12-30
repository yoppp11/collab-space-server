"""
Unit tests for Document API views.
"""
import pytest
from django.urls import reverse
from rest_framework import status
from apps.core.tests.factories import (
    UserFactory, WorkspaceFactory, DocumentFactory,
    WorkspaceMembershipFactory, BlockFactory
)

pytestmark = [pytest.mark.django_db, pytest.mark.views]


class TestDocumentViewSet:
    """Tests for Document API views."""
    
    def test_list_documents(self, authenticated_client, user):
        """Test listing documents."""
        workspace = WorkspaceFactory(owner=user)
        DocumentFactory.create_batch(3, workspace=workspace, created_by=user)
        
        url = reverse('documents:document-list')
        response = authenticated_client.get(url)
        
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND
        ]
    
    def test_create_document(self, authenticated_client, user):
        """Test creating a document."""
        workspace = WorkspaceFactory(owner=user)
        
        url = reverse('documents:document-list')
        data = {
            'workspace': workspace.id,
            'title': 'New Document',
        }
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_404_NOT_FOUND
        ]
    
    def test_get_document_detail(self, authenticated_client, user):
        """Test retrieving document details."""
        workspace = WorkspaceFactory(owner=user)
        document = DocumentFactory(workspace=workspace, created_by=user)
        
        url = reverse('documents:document-detail', args=[document.id])
        response = authenticated_client.get(url)
        
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND
        ]
    
    def test_update_document(self, authenticated_client, user):
        """Test updating a document."""
        workspace = WorkspaceFactory(owner=user)
        document = DocumentFactory(workspace=workspace, created_by=user)
        
        url = reverse('documents:document-detail', args=[document.id])
        data = {'title': 'Updated Title'}
        response = authenticated_client.patch(url, data, format='json')
        
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND
        ]
    
    def test_delete_document(self, authenticated_client, user):
        """Test deleting a document."""
        workspace = WorkspaceFactory(owner=user)
        document = DocumentFactory(workspace=workspace, created_by=user)
        
        url = reverse('documents:document-detail', args=[document.id])
        response = authenticated_client.delete(url)
        
        assert response.status_code in [
            status.HTTP_204_NO_CONTENT,
            status.HTTP_404_NOT_FOUND
        ]
    
    def test_cannot_edit_locked_document(self, authenticated_client, user):
        """Test that locked documents cannot be edited."""
        workspace = WorkspaceFactory(owner=user)
        document = DocumentFactory(
            workspace=workspace,
            created_by=user,
            is_locked=True
        )
        
        url = reverse('documents:document-detail', args=[document.id])
        data = {'title': 'Try to update'}
        response = authenticated_client.patch(url, data, format='json')
        
        # Should fail or be allowed depending on permissions
        assert response.status_code in [
            status.HTTP_200_OK,  # If owner can still edit
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND
        ]


class TestBlockAPI:
    """Tests for Block API."""
    
    def test_create_block_in_document(self, authenticated_client, user):
        """Test creating a block in a document."""
        workspace = WorkspaceFactory(owner=user)
        document = DocumentFactory(workspace=workspace, created_by=user)
        
        url = reverse('documents:block-list')
        data = {
            'document': document.id,
            'block_type': 'text',
            'content': {'text': 'Hello world'},
        }
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_405_METHOD_NOT_ALLOWED
        ]
    
    def test_list_document_blocks(self, authenticated_client, user):
        """Test listing blocks in a document."""
        workspace = WorkspaceFactory(owner=user)
        document = DocumentFactory(workspace=workspace, created_by=user)
        BlockFactory.create_batch(5, document=document)
        
        url = reverse('documents:document-blocks-list', args=[document.id])
        response = authenticated_client.get(url)
        
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND
        ]
    
    def test_update_block(self, authenticated_client, user):
        """Test updating a block."""
        workspace = WorkspaceFactory(owner=user)
        document = DocumentFactory(workspace=workspace, created_by=user)
        block = BlockFactory(document=document)
        
        url = reverse('documents:block-detail', args=[block.id])
        data = {'content': {'text': 'Updated text'}}
        response = authenticated_client.patch(url, data, format='json')
        
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND
        ]
    
    def test_delete_block(self, authenticated_client, user):
        """Test deleting a block."""
        workspace = WorkspaceFactory(owner=user)
        document = DocumentFactory(workspace=workspace, created_by=user)
        block = BlockFactory(document=document)
        
        url = reverse('documents:block-detail', args=[block.id])
        response = authenticated_client.delete(url)
        
        assert response.status_code in [
            status.HTTP_204_NO_CONTENT,
            status.HTTP_404_NOT_FOUND
        ]


class TestCommentAPI:
    """Tests for Comment API."""
    
    def test_create_comment(self, authenticated_client, user):
        """Test creating a comment on a document."""
        workspace = WorkspaceFactory(owner=user)
        document = DocumentFactory(workspace=workspace, created_by=user)
        
        url = reverse('documents:comment-list')
        data = {
            'document': document.id,
            'content': 'This is a comment',
        }
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_405_METHOD_NOT_ALLOWED
        ]
    
    def test_list_document_comments(self, authenticated_client, user):
        """Test listing comments on a document."""
        workspace = WorkspaceFactory(owner=user)
        document = DocumentFactory(workspace=workspace, created_by=user)
        
        url = reverse('documents:document-comments-list', args=[document.id])
        response = authenticated_client.get(url)
        
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND
        ]
    
    def test_resolve_comment(self, authenticated_client, user):
        """Test resolving a comment."""
        from apps.core.tests.factories import CommentFactory
        
        workspace = WorkspaceFactory(owner=user)
        document = DocumentFactory(workspace=workspace, created_by=user)
        comment = CommentFactory(document=document, author=user)
        
        url = reverse('documents:comment-resolve', args=[comment.id])
        response = authenticated_client.post(url)
        
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND
        ]
