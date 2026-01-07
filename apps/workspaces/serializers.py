"""
Workspace Serializers
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db import models
from django.utils.text import slugify
import secrets

from .models import (
    Workspace, WorkspaceMembership, WorkspaceInvitation,
    Board, BoardMembership, BoardList, WorkspaceRole, Card, CardComment
)
from apps.users.serializers import UserPublicSerializer

User = get_user_model()


class WorkspaceMembershipSerializer(serializers.ModelSerializer):
    """Serializer for workspace memberships."""
    user = UserPublicSerializer(read_only=True)
    invited_by = UserPublicSerializer(read_only=True)
    
    class Meta:
        model = WorkspaceMembership
        fields = ['id', 'user', 'role', 'invited_by', 'joined_at', 'is_active']
        read_only_fields = ['id', 'joined_at']


class WorkspaceSerializer(serializers.ModelSerializer):
    """Full workspace serializer."""
    owner = UserPublicSerializer(read_only=True)
    member_count = serializers.SerializerMethodField()
    board_count = serializers.SerializerMethodField()
    document_count = serializers.SerializerMethodField()
    current_user_role = serializers.SerializerMethodField()
    
    class Meta:
        model = Workspace
        fields = [
            'id', 'name', 'slug', 'description',
            'icon', 'icon_color', 'cover_image',
            'owner', 'is_public', 'settings',
            'member_count', 'board_count', 'document_count', 'current_user_role',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'slug', 'owner', 'created_at', 'updated_at']
    
    def get_member_count(self, obj):
        return obj.get_member_count()
    
    def get_board_count(self, obj):
        return obj.boards.filter(is_deleted=False).count()
    
    def get_document_count(self, obj):
        # Count documents in this workspace
        if hasattr(obj, 'documents'):
            return obj.documents.filter(is_deleted=False).count()
        return 0
    
    def get_current_user_role(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            membership = obj.memberships.filter(user=request.user).first()
            return membership.role if membership else None
        return None


class WorkspaceCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating workspaces."""
    
    class Meta:
        model = Workspace
        fields = ['name', 'description', 'icon', 'icon_color', 'is_public']
    
    def create(self, validated_data):
        from apps.core.cache import CacheManager
        
        user = self.context['request'].user
        
        # Generate unique slug
        base_slug = slugify(validated_data['name'])
        slug = base_slug
        counter = 1
        while Workspace.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        
        workspace = Workspace.objects.create(
            **validated_data,
            slug=slug,
            owner=user
        )
        
        # Add creator as owner member
        WorkspaceMembership.objects.create(
            workspace=workspace,
            user=user,
            role=WorkspaceRole.OWNER
        )
        
        # Invalidate user's workspace list cache for immediate display
        CacheManager.invalidate_user_workspaces(str(user.id))
        
        return workspace


class WorkspaceInvitationSerializer(serializers.ModelSerializer):
    """Serializer for workspace invitations."""
    workspace_name = serializers.CharField(source='workspace.name', read_only=True)
    invited_by = UserPublicSerializer(read_only=True)
    invite_link = serializers.SerializerMethodField()
    
    class Meta:
        model = WorkspaceInvitation
        fields = [
            'id', 'workspace', 'workspace_name', 'email', 'role',
            'invited_by', 'status', 'token', 'invite_link', 'message', 'expires_at', 'created_at'
        ]
        read_only_fields = ['id', 'workspace', 'invited_by', 'status', 'token', 'expires_at', 'created_at']
    
    def get_invite_link(self, obj):
        request = self.context.get('request')
        if request:
            base_url = f"{request.scheme}://{request.get_host()}"
            return f"{base_url}/invite/{obj.token}"
        return f"/invite/{obj.token}"


class InviteMemberSerializer(serializers.Serializer):
    """Serializer for inviting members."""
    email = serializers.EmailField(required=False, allow_blank=True)
    role = serializers.ChoiceField(choices=WorkspaceRole.choices, default=WorkspaceRole.MEMBER)
    message = serializers.CharField(required=False, allow_blank=True)


class GenerateInviteLinkSerializer(serializers.Serializer):
    """Serializer for generating an invite link."""
    role = serializers.ChoiceField(choices=WorkspaceRole.choices, default=WorkspaceRole.MEMBER)


class CardMinimalSerializer(serializers.ModelSerializer):
    """Minimal serializer for cards (used in lists)."""
    comment_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Card
        fields = ['id', 'list', 'title', 'description', 'status', 'color', 'due_date', 'position', 'labels', 'is_archived', 'comment_count']
    
    def get_comment_count(self, obj):
        return obj.comments.count()


class BoardListSerializer(serializers.ModelSerializer):
    """Serializer for board lists."""
    card_count = serializers.SerializerMethodField()
    cards = serializers.SerializerMethodField()
    
    class Meta:
        model = BoardList
        fields = ['id', 'name', 'color', 'status', 'position', 'wip_limit', 'card_count', 'cards']
    
    def get_card_count(self, obj):
        return obj.board_cards.filter(is_archived=False).count() if hasattr(obj, 'board_cards') else 0
    
    def get_cards(self, obj):
        if hasattr(obj, 'board_cards'):
            cards = obj.board_cards.filter(is_archived=False).order_by('position')
            return CardMinimalSerializer(cards, many=True).data
        return []


class BoardSerializer(serializers.ModelSerializer):
    """Full board serializer."""
    created_by = UserPublicSerializer(read_only=True)
    lists = BoardListSerializer(many=True, read_only=True)
    children = serializers.SerializerMethodField()
    
    class Meta:
        model = Board
        fields = [
            'id', 'workspace', 'name', 'description', 'board_type',
            'icon', 'color', 'cover_image', 'parent', 'position',
            'is_private', 'settings', 'created_by', 'lists', 'children',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'workspace', 'created_by', 'created_at', 'updated_at']
    
    def get_children(self, obj):
        children = obj.children.filter(is_deleted=False)
        return BoardSerializer(children, many=True, context=self.context).data


class BoardCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating boards."""
    
    class Meta:
        model = Board
        fields = ['name', 'description', 'board_type', 'icon', 'color', 'parent', 'is_private']
    
    def create(self, validated_data):
        from apps.core.cache import CacheManager
        
        workspace = self.context['workspace']
        user = self.context['request'].user
        
        # Get max position
        max_position = Board.objects.filter(
            workspace=workspace,
            parent=validated_data.get('parent')
        ).aggregate(max_pos=models.Max('position'))['max_pos'] or 0
        
        board = Board.objects.create(
            **validated_data,
            workspace=workspace,
            created_by=user,
            position=max_position + 1
        )
        
        # Invalidate workspace boards cache for immediate display
        CacheManager.invalidate_workspace_boards(str(workspace.id))
        
        return board


class BoardListCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating board lists."""
    
    class Meta:
        model = BoardList
        fields = ['name', 'color', 'status']
    
    def create(self, validated_data):
        from apps.core.cache import CacheManager
        
        board = self.context['board']
        
        max_position = BoardList.objects.filter(
            board=board
        ).aggregate(max_pos=models.Max('position'))['max_pos'] or 0
        
        board_list = BoardList.objects.create(
            **validated_data,
            board=board,
            position=max_position + 1
        )
        
        # Invalidate board detail cache for immediate display
        CacheManager.invalidate_board_detail(str(board.id))
        
        return board_list


class CardSerializer(serializers.ModelSerializer):
    """Serializer for cards."""
    created_by = UserPublicSerializer(read_only=True)
    assignees = UserPublicSerializer(many=True, read_only=True)
    comment_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Card
        fields = [
            'id', 'list', 'title', 'description', 'status', 'color', 'cover_image',
            'due_date', 'labels', 'assignees', 'created_by', 'is_archived',
            'position', 'comment_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']
    
    def get_comment_count(self, obj):
        return obj.comments.count()


class CardCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating cards."""
    
    class Meta:
        model = Card
        fields = ['title', 'description', 'status', 'color', 'due_date', 'labels']
    
    def create(self, validated_data):
        from apps.core.cache import CacheManager
        
        board_list = self.context['list']
        user = self.context['request'].user
        
        max_position = Card.objects.filter(
            list=board_list
        ).aggregate(max_pos=models.Max('position'))['max_pos'] or 0
        
        card = Card.objects.create(
            **validated_data,
            list=board_list,
            created_by=user,
            position=max_position + 1
        )
        
        # Invalidate board cards cache for immediate display
        CacheManager.invalidate_board_cards(str(board_list.board_id), str(board_list.id))
        CacheManager.invalidate_board_detail(str(board_list.board_id))
        
        return card


class BoardListDetailSerializer(serializers.ModelSerializer):
    """Serializer for board lists with cards."""
    card_count = serializers.SerializerMethodField()
    cards = serializers.SerializerMethodField()
    
    class Meta:
        model = BoardList
        fields = ['id', 'name', 'color', 'status', 'position', 'wip_limit', 'card_count', 'cards']
    
    def get_card_count(self, obj):
        return obj.board_cards.filter(is_archived=False).count() if hasattr(obj, 'board_cards') else 0
    
    def get_cards(self, obj):
        if hasattr(obj, 'board_cards'):
            cards = obj.board_cards.filter(is_archived=False).order_by('position')
            return CardSerializer(cards, many=True, context=self.context).data
        return []


class CardCommentSerializer(serializers.ModelSerializer):
    """Serializer for card comments."""
    author = UserPublicSerializer(read_only=True)
    mentions = UserPublicSerializer(many=True, read_only=True)
    mention_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False
    )
    
    class Meta:
        model = CardComment
        fields = [
            'id', 'card', 'author', 'text', 'images', 'mentions', 'mention_ids',
            'parent', 'is_edited', 'edited_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'author', 'is_edited', 'edited_at', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        mention_ids = validated_data.pop('mention_ids', [])
        user = self.context['request'].user
        
        comment = CardComment.objects.create(
            author=user,
            **validated_data
        )
        
        # Add mentioned users
        if mention_ids:
            comment.mentions.set(mention_ids)
        
        return comment
    
    def update(self, instance, validated_data):
        from django.utils import timezone
        
        mention_ids = validated_data.pop('mention_ids', None)
        
        # Update text if provided
        if 'text' in validated_data:
            instance.text = validated_data['text']
            instance.is_edited = True
            instance.edited_at = timezone.now()
        
        instance.save()
        
        # Update mentions if provided
        if mention_ids is not None:
            instance.mentions.set(mention_ids)
        
        return instance


class CardCommentCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating card comments."""
    mention_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False
    )
    
    class Meta:
        model = CardComment
        fields = ['text', 'images', 'mention_ids', 'parent']
    
    def create(self, validated_data):
        mention_ids = validated_data.pop('mention_ids', [])
        card = self.context['card']
        user = self.context['request'].user
        
        comment = CardComment.objects.create(
            card=card,
            author=user,
            **validated_data
        )
        
        # Add mentioned users
        if mention_ids:
            comment.mentions.set(mention_ids)
        
        return comment
