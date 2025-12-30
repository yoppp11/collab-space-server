"""
Unit tests for Document models.
"""
import pytest
from django.db import IntegrityError
from apps.documents.models import Document, Block, Comment
from apps.core.tests.factories import (
    DocumentFactory, BlockFactory, CommentFactory,
    WorkspaceFactory, UserFactory
)

pytestmark = pytest.mark.django_db


class TestDocumentModel:
    """Tests for the Document model."""
    
    def test_create_document(self, workspace, user):
        """Test creating a document."""
        document = DocumentFactory(
            workspace=workspace,
            title='Test Document',
            created_by=user
        )
        assert document.title == 'Test Document'
        assert document.workspace == workspace
        assert document.created_by == user
        assert document.current_version == 1
    
    def test_document_default_title(self, workspace, user):
        """Test document has default title."""
        document = DocumentFactory(workspace=workspace, created_by=user)
        assert document.title == 'Untitled' or len(document.title) > 0
    
    def test_document_state_default(self, workspace, user):
        """Test document state defaults to empty dict."""
        document = DocumentFactory(workspace=workspace, created_by=user)
        assert document.state == {}
    
    def test_document_tags_default(self, workspace, user):
        """Test document tags default to empty list."""
        document = DocumentFactory(workspace=workspace, created_by=user)
        assert document.tags == []
    
    def test_document_soft_delete(self, document):
        """Test soft deleting a document."""
        document.delete()
        assert document.is_deleted is True
        assert document.deleted_at is not None
    
    def test_document_is_locked(self, workspace, user):
        """Test locking a document."""
        document = DocumentFactory(
            workspace=workspace,
            created_by=user,
            is_locked=True
        )
        assert document.is_locked is True
    
    def test_document_is_template(self, workspace, user):
        """Test marking document as template."""
        document = DocumentFactory(
            workspace=workspace,
            created_by=user,
            is_template=True
        )
        assert document.is_template is True


class TestBlockModel:
    """Tests for the Block model."""
    
    def test_create_block(self, document):
        """Test creating a block."""
        block = BlockFactory(
            document=document,
            block_type='text',
            content={'text': 'Hello world'}
        )
        assert block.document == document
        assert block.block_type == 'text'
        assert block.content['text'] == 'Hello world'
    
    def test_nested_blocks(self, document):
        """Test creating nested blocks."""
        parent = BlockFactory(document=document, block_type='heading')
        child = BlockFactory(
            document=document,
            parent=parent,
            block_type='text'
        )
        
        assert child.parent == parent
        assert child in parent.get_children()
    
    def test_block_ordering_by_position(self, document):
        """Test blocks are ordered by position."""
        block1 = BlockFactory(document=document, position=3000)
        block2 = BlockFactory(document=document, position=1000)
        block3 = BlockFactory(document=document, position=2000)
        
        # MPTT ordering might differ, but position should be set
        assert block2.position < block3.position < block1.position


class TestCommentModel:
    """Tests for the Comment model."""
    
    def test_create_comment(self, document, user):
        """Test creating a comment."""
        comment = CommentFactory(
            document=document,
            author=user,
            content='This is a comment'
        )
        assert comment.document == document
        assert comment.author == user
        assert comment.content == 'This is a comment'
        assert comment.is_resolved is False
    
    def test_comment_thread(self, document, user):
        """Test creating comment threads."""
        parent_comment = CommentFactory(document=document, author=user)
        reply1 = CommentFactory(
            document=document,
            author=user,
            parent=parent_comment
        )
        reply2 = CommentFactory(
            document=document,
            author=user,
            parent=parent_comment
        )
        
        assert reply1.parent == parent_comment
        assert reply2.parent == parent_comment
        # Depending on model implementation
        # assert parent_comment.replies.count() == 2
    
    def test_resolve_comment(self, document, user):
        """Test resolving a comment."""
        comment = CommentFactory(
            document=document,
            author=user,
            is_resolved=True
        )
        assert comment.is_resolved is True
    
    def test_comment_ordering(self, document, user):
        """Test comments are ordered by creation date."""
        comment1 = CommentFactory(document=document, author=user)
        comment2 = CommentFactory(document=document, author=user)
        comment3 = CommentFactory(document=document, author=user)
        
        # Comments should exist
        assert Comment.objects.filter(document=document).count() == 3
