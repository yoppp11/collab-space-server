"""
Document Services
"""
from typing import Optional
from django.db import transaction
from django.utils import timezone
from django.core.cache import cache
from .models import Document, Block, DocumentVersion
from apps.core.cache import CacheManager, CACHE_TIMEOUT_SHORT, CACHE_TIMEOUT_MEDIUM
import json


class DocumentService:
    """
    Service for document operations with caching support.
    """
    
    @staticmethod
    @transaction.atomic
    def create_document(user, workspace_id: str, title: str = 'Untitled', **kwargs) -> Document:
        """
        Create a new document.
        """
        document = Document.objects.create(
            workspace_id=workspace_id,
            title=title,
            created_by=user,
            last_edited_by=user,
            **kwargs
        )
        
        # Create initial title block
        Block.objects.create(
            document=document,
            block_type=Block.BlockType.HEADING_1,
            content={'text': title},
            text=title,
            position=0,
            created_by=user,
            last_edited_by=user
        )
        
        return document
    
    @staticmethod
    def get_document_with_blocks(document_id: str) -> Optional[Document]:
        """
        Get a document with its blocks, using cache.
        """
        cache_key = CacheManager.get_document_cache_key(document_id, "with_blocks")
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return cached_data
        
        document = Document.objects.filter(
            id=document_id,
            is_deleted=False
        ).prefetch_related(
            'blocks'
        ).select_related(
            'workspace', 'created_by', 'last_edited_by'
        ).first()
        
        if document:
            cache.set(cache_key, document, CACHE_TIMEOUT_SHORT)
        
        return document
    
    @staticmethod
    @transaction.atomic
    def duplicate_document(document: Document, user) -> Document:
        """
        Duplicate a document with all its blocks.
        """
        new_document = Document.objects.create(
            workspace=document.workspace,
            board=document.board,
            title=f"{document.title} (Copy)",
            icon=document.icon,
            created_by=user,
            last_edited_by=user,
            properties=document.properties.copy(),
            tags=document.tags.copy()
        )
        
        # Duplicate all blocks
        blocks = document.blocks.all()
        block_mapping = {}
        
        for block in blocks:
            new_block = Block.objects.create(
                document=new_document,
                parent_id=block_mapping.get(block.parent_id) if block.parent_id else None,
                block_type=block.block_type,
                content=block.content.copy(),
                text=block.text,
                properties=block.properties.copy(),
                position=block.position,
                created_by=user,
                last_edited_by=user
            )
            block_mapping[block.id] = new_block.id
        
        return new_document
    
    @staticmethod
    def update_document(document: Document, user, **kwargs) -> Document:
        """
        Update a document and invalidate cache.
        """
        for key, value in kwargs.items():
            setattr(document, key, value)
        document.last_edited_by = user
        document.save()
        
        # Invalidate caches
        CacheManager.invalidate_document_all(str(document.id))
        
        return document
    
    @staticmethod
    def create_version_snapshot(document: Document, user, change_summary: str = '') -> DocumentVersion:
        """
        Create a version snapshot of the document.
        """
        blocks_data = []
        for block in document.blocks.all():
            blocks_data.append({
                'id': str(block.id),
                'type': block.block_type,
                'content': block.content,
                'position': block.position,
                'parent_id': str(block.parent_id) if block.parent_id else None,
            })
        
        version = DocumentVersion.objects.create(
            document=document,
            version_number=document.current_version,
            title=document.title,
            state=document.state.copy(),
            blocks_snapshot=blocks_data,
            created_by=user,
            change_summary=change_summary,
            content_size=len(json.dumps(blocks_data))
        )
        
        return version


class BlockService:
    """
    Service for block operations with cache invalidation.
    """
    
    @staticmethod
    @transaction.atomic
    def create_block(
        document_id: str,
        user,
        block_type: str,
        content: dict,
        parent_id: Optional[str] = None,
        **kwargs
    ) -> Block:
        """
        Create a new block.
        """
        from django.db.models import Max
        
        # Get max position for siblings
        siblings = Block.objects.filter(
            document_id=document_id,
            parent_id=parent_id
        )
        max_position = siblings.aggregate(Max('position'))['position__max'] or 0
        
        # Extract plain text from content
        text = BlockService._extract_text(content)
        
        block = Block.objects.create(
            document_id=document_id,
            parent_id=parent_id,
            block_type=block_type,
            content=content,
            text=text,
            position=max_position + 1,
            created_by=user,
            last_edited_by=user,
            **kwargs
        )
        
        # Invalidate document cache
        CacheManager.invalidate_document_blocks(document_id)
        
        return block
    
    @staticmethod
    def update_block(block: Block, user, **kwargs) -> Block:
        """
        Update a block and invalidate cache.
        """
        for key, value in kwargs.items():
            if key == 'content':
                block.content = value
                block.text = BlockService._extract_text(value)
            else:
                setattr(block, key, value)
        
        block.last_edited_by = user
        block.save()
        
        # Invalidate document cache
        CacheManager.invalidate_document_blocks(str(block.document_id))
        
        return block
    
    @staticmethod
    def delete_block(block: Block) -> bool:
        """
        Delete a block and invalidate cache.
        """
        document_id = str(block.document_id)
        block.delete()
        
        # Invalidate document cache
        CacheManager.invalidate_document_blocks(document_id)
        
        return True
    
    @staticmethod
    def _extract_text(content: dict) -> str:
        """
        Extract plain text from rich content.
        """
        if isinstance(content, dict):
            if 'text' in content:
                return content['text']
            if 'blocks' in content:
                # Prosemirror/Slate format
                texts = []
                for block in content['blocks']:
                    if 'text' in block:
                        texts.append(block['text'])
                return ' '.join(texts)
        return str(content)
