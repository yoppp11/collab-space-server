"""
Document Serializers
"""
from rest_framework import serializers
from .models import Document, Block, DocumentVersion, Comment, Attachment
from apps.users.serializers import UserPublicSerializer


class BlockSerializer(serializers.ModelSerializer):
    """Serializer for content blocks."""
    created_by = UserPublicSerializer(read_only=True)
    last_edited_by = UserPublicSerializer(read_only=True)
    children = serializers.SerializerMethodField()
    
    class Meta:
        model = Block
        fields = [
            'id', 'document', 'parent', 'block_type',
            'content', 'text', 'properties', 'position',
            'level', 'lft', 'rght', 'tree_id',
            'created_by', 'last_edited_by', 'version',
            'children', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'level', 'lft', 'rght', 'tree_id', 'created_at', 'updated_at']
    
    def get_children(self, obj):
        if hasattr(obj, 'prefetched_children'):
            return BlockSerializer(obj.prefetched_children, many=True).data
        children = obj.get_children()
        return BlockSerializer(children, many=True).data


class DocumentSerializer(serializers.ModelSerializer):
    """Full document serializer."""
    created_by = UserPublicSerializer(read_only=True)
    last_edited_by = UserPublicSerializer(read_only=True)
    blocks = BlockSerializer(many=True, read_only=True)
    
    class Meta:
        model = Document
        fields = [
            'id', 'workspace', 'board', 'board_list',
            'title', 'icon', 'cover_image', 'cover_position',
            'created_by', 'last_edited_by', 'last_edited_at',
            'current_version', 'is_template', 'is_locked', 'is_public',
            'tags', 'position', 'due_date', 'properties',
            'blocks', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_by', 'last_edited_by', 'last_edited_at', 'current_version']


class DocumentListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for document lists."""
    created_by = UserPublicSerializer(read_only=True)
    last_edited_by = UserPublicSerializer(read_only=True)
    
    class Meta:
        model = Document
        fields = [
            'id', 'title', 'icon', 'created_by', 'last_edited_by',
            'last_edited_at', 'is_locked', 'tags', 'created_at'
        ]


class CommentSerializer(serializers.ModelSerializer):
    """Serializer for comments."""
    author = UserPublicSerializer(read_only=True)
    resolved_by = UserPublicSerializer(read_only=True)
    replies = serializers.SerializerMethodField()
    
    class Meta:
        model = Comment
        fields = [
            'id', 'document', 'block', 'parent', 'author',
            'content', 'text', 'is_resolved', 'resolved_by', 'resolved_at',
            'replies', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'author', 'resolved_by', 'resolved_at']
    
    def get_replies(self, obj):
        if obj.parent is None:
            replies = obj.replies.filter(is_deleted=False).order_by('created_at')
            return CommentSerializer(replies, many=True).data
        return []


class AttachmentSerializer(serializers.ModelSerializer):
    """Serializer for attachments."""
    uploaded_by = UserPublicSerializer(read_only=True)
    
    class Meta:
        model = Attachment
        fields = [
            'id', 'document', 'block', 'uploaded_by',
            'file', 'filename', 'file_size', 'mime_type',
            'width', 'height', 'duration', 'created_at'
        ]
        read_only_fields = ['id', 'uploaded_by', 'file_size', 'mime_type']
