"""
Performance tests for critical operations.
"""
import pytest
import time
from django.utils import timezone
from apps.core.tests.factories import (
    UserFactory, WorkspaceFactory, DocumentFactory,
    BlockFactory
)

pytestmark = [pytest.mark.django_db, pytest.mark.slow]


class TestPerformance:
    """Performance tests for critical operations."""
    
    def test_bulk_user_creation_performance(self):
        """Test performance of creating many users."""
        start_time = time.time()
        
        users = UserFactory.create_batch(100)
        
        duration = time.time() - start_time
        
        assert len(users) == 100
        assert duration < 5.0  # Should complete in under 5 seconds
    
    def test_workspace_query_performance(self, user):
        """Test performance of querying workspaces."""
        # Create workspaces
        workspaces = WorkspaceFactory.create_batch(50, owner=user)
        
        start_time = time.time()
        
        # Query all workspaces
        result = list(user.owned_workspaces.all())
        
        duration = time.time() - start_time
        
        assert len(result) == 50
        assert duration < 1.0  # Should complete in under 1 second
    
    def test_document_with_many_blocks_performance(self, workspace, user):
        """Test performance with documents containing many blocks."""
        document = DocumentFactory(workspace=workspace, created_by=user)
        
        start_time = time.time()
        
        # Create many blocks
        blocks = BlockFactory.create_batch(100, document=document)
        
        duration = time.time() - start_time
        
        assert document.blocks.count() == 100
        assert duration < 10.0  # Should complete in under 10 seconds
    
    def test_nested_block_query_performance(self, workspace, user):
        """Test performance of querying nested blocks."""
        document = DocumentFactory(workspace=workspace, created_by=user)
        
        # Create nested structure
        parent = BlockFactory(document=document)
        for _ in range(10):
            child = BlockFactory(document=document, parent=parent)
            for _ in range(5):
                BlockFactory(document=document, parent=child)
        
        start_time = time.time()
        
        # Query all blocks for document
        blocks = list(document.blocks.all())
        
        duration = time.time() - start_time
        
        assert len(blocks) > 50
        assert duration < 2.0  # Should complete in under 2 seconds
