"""
Tests for Document Services
"""
import pytest
from apps.documents.services import DocumentService, BlockService
from apps.documents.models import Document, Block, DocumentVersion
from apps.core.tests.factories import (
    UserFactory,
    WorkspaceFactory,
    DocumentFactory,
    BlockFactory,
)


@pytest.mark.django_db
class TestDocumentService:
    """Test document service methods"""
    
    def test_create_document(self):
        """Test creating a document with initial block"""
        user = UserFactory()
        workspace = WorkspaceFactory()
        
        document = DocumentService.create_document(
            user=user,
            workspace_id=str(workspace.id),
            title='Test Document'
        )
        
        assert document.title == 'Test Document'
        assert document.workspace == workspace
        assert document.created_by == user
        assert document.last_edited_by == user
        
        # Verify initial title block created
        blocks = Block.objects.filter(document=document)
        assert blocks.count() == 1
        assert blocks.first().block_type == Block.BlockType.HEADING_1
        assert blocks.first().text == 'Test Document'
    
    def test_create_document_with_kwargs(self):
        """Test creating document with additional kwargs"""
        user = UserFactory()
        workspace = WorkspaceFactory()
        
        document = DocumentService.create_document(
            user=user,
            workspace_id=str(workspace.id),
            title='Doc',
            icon='📄',
            tags=['tag1', 'tag2']
        )
        
        assert document.icon == '📄'
        assert document.tags == ['tag1', 'tag2']
    
    def test_duplicate_document(self):
        """Test duplicating a document with all blocks"""
        user = UserFactory()
        original_doc = DocumentFactory(
            title='Original',
            icon='📄',
            tags=['tag1'],
            properties={'key': 'value'}
        )
        
        # Create some blocks
        block1 = BlockFactory(
            document=original_doc,
            block_type='paragraph',
            content={'text': 'Block 1'},
            position=0
        )
        block2 = BlockFactory(
            document=original_doc,
            block_type='paragraph',
            content={'text': 'Block 2'},
            position=1,
            parent=block1
        )
        
        # Duplicate
        duplicate = DocumentService.duplicate_document(original_doc, user)
        
        assert duplicate.title == 'Original (Copy)'
        assert duplicate.icon == '📄'
        assert duplicate.tags == ['tag1']
        assert duplicate.properties == {'key': 'value'}
        assert duplicate.workspace == original_doc.workspace
        
        # Verify blocks duplicated
        dup_blocks = list(duplicate.blocks.all().order_by('position'))
        assert len(dup_blocks) == 2
        assert dup_blocks[0].content == {'text': 'Block 1'}
        assert dup_blocks[1].content == {'text': 'Block 2'}
        
        # Verify parent relationship maintained
        assert dup_blocks[1].parent_id == dup_blocks[0].id
    
    def test_create_version_snapshot(self):
        """Test creating version snapshot"""
        user = UserFactory()
        document = DocumentFactory(current_version=5)
        
        # Create blocks
        block1 = BlockFactory(
            document=document,
            block_type='heading',
            content={'text': 'Title'},
            position=0
        )
        block2 = BlockFactory(
            document=document,
            block_type='paragraph',
            content={'text': 'Content'},
            position=1,
            parent=block1
        )
        
        # Create snapshot
        version = DocumentService.create_version_snapshot(
            document=document,
            user=user,
            change_summary='Test snapshot'
        )
        
        assert version.document == document
        assert version.version_number == 5
        assert version.title == document.title
        assert version.created_by == user
        assert version.change_summary == 'Test snapshot'
        
        # Verify blocks snapshot
        assert len(version.blocks_snapshot) == 2
        assert version.blocks_snapshot[0]['type'] == 'heading'
        assert version.blocks_snapshot[1]['type'] == 'paragraph'
        assert version.content_size > 0


@pytest.mark.django_db
class TestBlockService:
    """Test block service methods"""
    
    def test_create_block(self):
        """Test creating a block"""
        document = DocumentFactory()
        user = UserFactory()
        
        block = BlockService.create_block(
            document_id=str(document.id),
            user=user,
            block_type='paragraph',
            content={'text': 'Hello world'}
        )
        
        assert block.document == document
        assert block.block_type == 'paragraph'
        assert block.content == {'text': 'Hello world'}
        assert block.text == 'Hello world'
        assert block.position == 1
        assert block.created_by == user
    
    def test_create_block_with_parent(self):
        """Test creating nested block"""
        document = DocumentFactory()
        user = UserFactory()
        parent_block = BlockFactory(document=document)
        
        block = BlockService.create_block(
            document_id=str(document.id),
            user=user,
            block_type='paragraph',
            content={'text': 'Child block'},
            parent_id=str(parent_block.id)
        )
        
        assert block.parent == parent_block
    
    def test_create_block_position_increments(self):
        """Test block positions increment correctly"""
        document = DocumentFactory()
        user = UserFactory()
        
        # Create blocks (document already has one from factory)
        block1 = BlockService.create_block(
            document_id=str(document.id),
            user=user,
            block_type='paragraph',
            content={'text': 'First'}
        )
        
        block2 = BlockService.create_block(
            document_id=str(document.id),
            user=user,
            block_type='paragraph',
            content={'text': 'Second'}
        )
        
        assert block2.position > block1.position
    
    def test_extract_text_simple(self):
        """Test text extraction from simple content"""
        text = BlockService._extract_text({'text': 'Hello'})
        assert text == 'Hello'
    
    def test_extract_text_with_blocks(self):
        """Test text extraction from blocks format"""
        content = {
            'blocks': [
                {'text': 'First'},
                {'text': 'Second'},
            ]
        }
        text = BlockService._extract_text(content)
        assert text == 'First Second'
    
    def test_extract_text_fallback(self):
        """Test text extraction fallback"""
        text = BlockService._extract_text({'other': 'data'})
        assert text == "{'other': 'data'}"
