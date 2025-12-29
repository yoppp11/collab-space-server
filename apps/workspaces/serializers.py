"""
Workspace Serializers
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils.text import slugify
import secrets

from .models import (
    Workspace, WorkspaceMembership, WorkspaceInvitation,
    Board, BoardMembership, BoardList, WorkspaceRole
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
    current_user_role = serializers.SerializerMethodField()
    
    class Meta:
        model = Workspace
        fields = [
            'id', 'name', 'slug', 'description',
            'icon', 'icon_color', 'cover_image',
            'owner', 'is_public', 'settings',
            'member_count', 'current_user_role',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'slug', 'owner', 'created_at', 'updated_at']
    
    def get_member_count(self, obj):
        return obj.get_member_count()
    
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
        
        return workspace


class WorkspaceInvitationSerializer(serializers.ModelSerializer):
    """Serializer for workspace invitations."""
    workspace_name = serializers.CharField(source='workspace.name', read_only=True)
    invited_by = UserPublicSerializer(read_only=True)
    
    class Meta:
        model = WorkspaceInvitation
        fields = [
            'id', 'workspace', 'workspace_name', 'email', 'role',
            'invited_by', 'status', 'message', 'expires_at', 'created_at'
        ]
        read_only_fields = ['id', 'workspace', 'invited_by', 'status', 'expires_at', 'created_at']


class InviteMemberSerializer(serializers.Serializer):
    """Serializer for inviting members."""
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=WorkspaceRole.choices, default=WorkspaceRole.MEMBER)
    message = serializers.CharField(required=False, allow_blank=True)


class BoardListSerializer(serializers.ModelSerializer):
    """Serializer for board lists."""
    card_count = serializers.SerializerMethodField()
    
    class Meta:
        model = BoardList
        fields = ['id', 'name', 'color', 'position', 'wip_limit', 'card_count']
    
    def get_card_count(self, obj):
        return obj.cards.count() if hasattr(obj, 'cards') else 0


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
        
        return board


class BoardListCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating board lists."""
    
    class Meta:
        model = BoardList
        fields = ['name', 'color', 'wip_limit']
    
    def create(self, validated_data):
        board = self.context['board']
        
        max_position = BoardList.objects.filter(
            board=board
        ).aggregate(max_pos=models.Max('position'))['max_pos'] or 0
        
        return BoardList.objects.create(
            **validated_data,
            board=board,
            position=max_position + 1
        )
