"""
Document API Views
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from .models import Document, Block, Comment, Attachment
from .serializers import (
    DocumentSerializer, DocumentListSerializer,
    BlockSerializer, CommentSerializer, AttachmentSerializer
)
from .services import DocumentService, BlockService
from apps.workspaces.permissions import CanEditDocument, CanViewDocument


class DocumentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for document CRUD operations.
    """
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        workspace_id = self.request.query_params.get('workspace')
        queryset = Document.objects.filter(is_deleted=False)
        
        if workspace_id:
            queryset = queryset.filter(workspace_id=workspace_id)
        
        # Filter by user access
        return queryset.select_related(
            'workspace', 'created_by', 'last_edited_by'
        )
    
    def get_serializer_class(self):
        if self.action == 'list':
            return DocumentListSerializer
        return DocumentSerializer
    
    def get_permissions(self):
        if self.action in ['update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), CanEditDocument()]
        if self.action == 'retrieve':
            return [IsAuthenticated(), CanViewDocument()]
        return super().get_permissions()
    
    def create(self, request, *args, **kwargs):
        workspace_id = request.data.get('workspace')
        
        document = DocumentService.create_document(
            user=request.user,
            workspace_id=workspace_id,
            title=request.data.get('title', 'Untitled'),
            **{k: v for k, v in request.data.items() if k not in ['workspace', 'title']}
        )
        
        return Response({
            'success': True,
            'data': DocumentSerializer(document).data,
            'message': 'Document created successfully'
        }, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['get'])
    def versions(self, request, pk=None):
        """Get document version history."""
        document = self.get_object()
        versions = document.versions.all()[:20]
        
        return Response({
            'success': True,
            'data': [
                {
                    'version': v.version_number,
                    'created_by': v.created_by.display_name if v.created_by else None,
                    'created_at': v.created_at,
                    'change_summary': v.change_summary,
                }
                for v in versions
            ]
        })
    
    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """Duplicate a document."""
        document = self.get_object()
        
        new_document = DocumentService.duplicate_document(
            document=document,
            user=request.user
        )
        
        return Response({
            'success': True,
            'data': DocumentSerializer(new_document).data,
            'message': 'Document duplicated successfully'
        }, status=status.HTTP_201_CREATED)


class BlockViewSet(viewsets.ModelViewSet):
    """
    ViewSet for block operations.
    """
    serializer_class = BlockSerializer
    permission_classes = [IsAuthenticated, CanEditDocument]
    
    def get_queryset(self):
        document_id = self.kwargs.get('document_pk')
        return Block.objects.filter(document_id=document_id)
    
    def create(self, request, *args, **kwargs):
        document_id = self.kwargs.get('document_pk')
        
        block = BlockService.create_block(
            document_id=document_id,
            user=request.user,
            **request.data
        )
        
        return Response({
            'success': True,
            'data': BlockSerializer(block).data
        }, status=status.HTTP_201_CREATED)


class CommentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for comments.
    """
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        document_id = self.request.query_params.get('document')
        queryset = Comment.objects.filter(is_deleted=False, parent=None)
        
        if document_id:
            queryset = queryset.filter(document_id=document_id)
        
        return queryset.select_related('author', 'resolved_by')
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        comment = Comment.objects.create(
            **serializer.validated_data,
            author=request.user
        )
        
        return Response({
            'success': True,
            'data': CommentSerializer(comment).data
        }, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Resolve a comment."""
        comment = self.get_object()
        comment.is_resolved = True
        comment.resolved_by = request.user
        comment.resolved_at = timezone.now()
        comment.save()
        
        return Response({
            'success': True,
            'data': CommentSerializer(comment).data
        })
