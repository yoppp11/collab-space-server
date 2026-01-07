"""
Workspace API Views
"""
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.core.cache import cache

from .models import (
    Workspace, WorkspaceMembership, WorkspaceInvitation,
    Board, BoardList, Card, CardComment
)
from .serializers import (
    WorkspaceSerializer, WorkspaceCreateSerializer,
    WorkspaceMembershipSerializer, WorkspaceInvitationSerializer,
    InviteMemberSerializer, BoardSerializer, BoardCreateSerializer,
    BoardListSerializer, BoardListCreateSerializer, GenerateInviteLinkSerializer,
    CardSerializer, CardCreateSerializer, CardCommentSerializer, CardCommentCreateSerializer
)
from .services import WorkspaceService, BoardService, WorkspaceSelector
from .permissions import (
    IsWorkspaceMember, IsWorkspaceAdmin, IsWorkspaceOwner,
    get_workspace_role
)
from apps.core.cache import CacheManager, CACHE_TIMEOUT_SHORT, CACHE_TIMEOUT_MEDIUM


class WorkspaceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for workspace CRUD operations.
    """
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return WorkspaceService.get_user_workspaces(self.request.user)
    
    def get_serializer_class(self):
        if self.action == 'create':
            return WorkspaceCreateSerializer
        return WorkspaceSerializer
    
    def get_permissions(self):
        if self.action in ['update', 'partial_update']:
            return [IsAuthenticated(), IsWorkspaceAdmin()]
        if self.action == 'destroy':
            return [IsAuthenticated(), IsWorkspaceOwner()]
        return super().get_permissions()
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        workspace = serializer.save()
        
        return Response({
            'success': True,
            'data': WorkspaceSerializer(workspace, context={'request': request}).data,
            'message': 'Workspace created successfully'
        }, status=status.HTTP_201_CREATED)
    
    def update(self, request, *args, **kwargs):
        """Update a workspace."""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        workspace = serializer.save()
        
        # Invalidate cache for immediate display
        CacheManager.invalidate_workspace_detail(str(workspace.id))
        # Also invalidate user's workspace list to update workspace name/details
        CacheManager.invalidate_user_workspaces(str(request.user.id))
        
        return Response(serializer.data)
    
    def destroy(self, request, *args, **kwargs):
        """Delete a workspace (soft delete)."""
        workspace = self.get_object()
        user_id = str(request.user.id)
        
        # Soft delete
        workspace.is_deleted = True
        workspace.save()
        
        # Invalidate cache for immediate display
        CacheManager.invalidate_user_workspaces(user_id)
        CacheManager.invalidate_workspace_all(str(workspace.id))
        
        return Response({
            'success': True,
            'message': 'Workspace deleted successfully'
        }, status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=True, methods=['get'])
    def members(self, request, pk=None):
        """List workspace members."""
        workspace = self.get_object()
        members = WorkspaceSelector.get_workspace_members(workspace)
        serializer = WorkspaceMembershipSerializer(members, many=True)
        
        return Response({
            'success': True,
            'data': serializer.data
        })
    
    @action(detail=True, methods=['post'], url_path='generate-invite-link')
    def generate_invite_link(self, request, pk=None):
        """Generate an invite link for the workspace."""
        workspace = self.get_object()
        
        # Check permission
        role = get_workspace_role(request.user, workspace)
        if role not in ['owner', 'admin']:
            return Response({
                'success': False,
                'error': {'message': 'Permission denied'}
            }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = GenerateInviteLinkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            invitation = WorkspaceService.generate_invite_link(
                workspace=workspace,
                role=serializer.validated_data['role'],
                invited_by=request.user
            )
            
            return Response({
                'success': True,
                'data': WorkspaceInvitationSerializer(invitation, context={'request': request}).data,
                'message': 'Invite link generated successfully'
            }, status=status.HTTP_201_CREATED)
        except ValueError as e:
            return Response({
                'success': False,
                'error': {'message': str(e)}
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def invite(self, request, pk=None):
        """Invite a member to the workspace."""
        workspace = self.get_object()
        
        # Check permission
        role = get_workspace_role(request.user, workspace)
        if role not in ['owner', 'admin']:
            return Response({
                'success': False,
                'error': {'message': 'Permission denied'}
            }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = InviteMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            invitation = WorkspaceService.invite_member(
                workspace=workspace,
                email=serializer.validated_data.get('email', ''),
                role=serializer.validated_data['role'],
                invited_by=request.user,
                message=serializer.validated_data.get('message', '')
            )
            
            # TODO: Send invitation email via Celery task
            
            return Response({
                'success': True,
                'data': WorkspaceInvitationSerializer(invitation, context={'request': request}).data,
                'message': 'Invitation sent successfully'
            }, status=status.HTTP_201_CREATED)
        except ValueError as e:
            return Response({
                'success': False,
                'error': {'message': str(e)}
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'], url_path='members/(?P<user_id>[^/.]+)/role')
    def update_member_role(self, request, pk=None, user_id=None):
        """Update a member's role."""
        workspace = self.get_object()
        
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        user = get_object_or_404(User, id=user_id)
        new_role = request.data.get('role')
        
        try:
            membership = WorkspaceService.update_member_role(
                workspace=workspace,
                user=user,
                new_role=new_role,
                updated_by=request.user
            )
            
            return Response({
                'success': True,
                'data': WorkspaceMembershipSerializer(membership).data,
                'message': 'Role updated successfully'
            })
        except ValueError as e:
            return Response({
                'success': False,
                'error': {'message': str(e)}
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['delete'], url_path='members/(?P<user_id>[^/.]+)')
    def remove_member(self, request, pk=None, user_id=None):
        """Remove a member from the workspace."""
        workspace = self.get_object()
        
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        user = get_object_or_404(User, id=user_id)
        
        try:
            WorkspaceService.remove_member(
                workspace=workspace,
                user=user,
                removed_by=request.user
            )
            
            return Response({
                'success': True,
                'message': 'Member removed successfully'
            })
        except ValueError as e:
            return Response({
                'success': False,
                'error': {'message': str(e)}
            }, status=status.HTTP_400_BAD_REQUEST)


class InvitationAcceptView(generics.GenericAPIView):
    """
    Accept a workspace invitation.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, token):
        invitation = get_object_or_404(WorkspaceInvitation, token=token)
        
        try:
            membership = WorkspaceService.accept_invitation(
                invitation=invitation,
                user=request.user
            )
            
            # Send notifications to workspace members
            from apps.notifications.services import NotificationService
            NotificationService.notify_workspace_member_joined(
                workspace=invitation.workspace,
                new_member=request.user,
                invited_by=invitation.invited_by
            )
            
            return Response({
                'success': True,
                'data': WorkspaceMembershipSerializer(membership).data,
                'message': 'Invitation accepted'
            })
        except ValueError as e:
            return Response({
                'success': False,
                'error': {'message': str(e)}
            }, status=status.HTTP_400_BAD_REQUEST)


class JoinWorkspaceByCodeView(generics.GenericAPIView):
    """
    Join a workspace using an invite code.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        code = request.data.get('code', '').strip()
        
        if not code:
            return Response({
                'success': False,
                'error': {'message': 'Invite code is required'}
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Find invitation by token/code
        invitation = WorkspaceInvitation.objects.filter(token=code).first()
        
        if not invitation:
            return Response({
                'success': False,
                'error': {'message': 'Invalid invite code'}
            }, status=status.HTTP_404_NOT_FOUND)
        
        try:
            membership = WorkspaceService.accept_invitation(
                invitation=invitation,
                user=request.user
            )
            
            # Send notifications to workspace members
            from apps.notifications.services import NotificationService
            NotificationService.notify_workspace_member_joined(
                workspace=invitation.workspace,
                new_member=request.user,
                invited_by=invitation.invited_by
            )
            
            return Response({
                'success': True,
                'data': {
                    'membership': WorkspaceMembershipSerializer(membership).data,
                    'workspace': WorkspaceSerializer(invitation.workspace, context={'request': request}).data
                },
                'message': f'Successfully joined {invitation.workspace.name}'
            })
        except ValueError as e:
            return Response({
                'success': False,
                'error': {'message': str(e)}
            }, status=status.HTTP_400_BAD_REQUEST)


class BoardViewSet(viewsets.ModelViewSet):
    """
    ViewSet for board CRUD operations.
    """
    permission_classes = [IsAuthenticated, IsWorkspaceMember]
    
    def get_queryset(self):
        workspace_id = self.kwargs.get('workspace_pk')
        return Board.objects.filter(
            workspace_id=workspace_id,
            is_deleted=False
        ).order_by('position')
    
    def get_serializer_class(self):
        if self.action == 'create':
            return BoardCreateSerializer
        return BoardSerializer
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        workspace_id = self.kwargs.get('workspace_pk')
        context['workspace'] = get_object_or_404(Workspace, id=workspace_id)
        return context
    
    def create(self, request, *args, **kwargs):
        workspace = self.get_serializer_context()['workspace']
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        board = serializer.save()
        
        # Send notifications to workspace members
        from apps.notifications.services import NotificationService
        NotificationService.notify_board_created(
            workspace=workspace,
            board=board,
            creator=request.user
        )
        
        return Response({
            'success': True,
            'data': BoardSerializer(board, context={'request': request}).data,
            'message': 'Board created successfully'
        }, status=status.HTTP_201_CREATED)
    
    def update(self, request, *args, **kwargs):
        """Update a board."""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        board = serializer.save()
        
        # Invalidate cache for immediate display
        CacheManager.invalidate_workspace_boards(str(board.workspace_id))
        CacheManager.invalidate_board_detail(str(board.id))
        
        return Response(serializer.data)
    
    def destroy(self, request, *args, **kwargs):
        """Delete a board (soft delete)."""
        board = self.get_object()
        workspace_id = str(board.workspace_id)
        
        # Soft delete
        board.is_deleted = True
        board.save()
        
        # Invalidate cache for immediate display
        CacheManager.invalidate_workspace_boards(workspace_id)
        
        return Response({
            'success': True,
            'message': 'Board deleted successfully'
        }, status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=True, methods=['post'])
    def move(self, request, workspace_pk=None, pk=None):
        """Move a board to a new position."""
        board = self.get_object()
        new_position = request.data.get('position', 0)
        new_parent_id = request.data.get('parent_id')
        
        new_parent = None
        if new_parent_id:
            new_parent = get_object_or_404(Board, id=new_parent_id)
        
        BoardService.move_board(board, new_position, new_parent)
        
        return Response({
            'success': True,
            'data': BoardSerializer(board, context={'request': request}).data,
            'message': 'Board moved successfully'
        })


class BoardListViewSet(viewsets.ModelViewSet):
    """
    ViewSet for board lists (Kanban columns).
    """
    permission_classes = [IsAuthenticated]
    serializer_class = BoardListSerializer
    
    def get_queryset(self):
        board_id = self.kwargs.get('board_pk')
        return BoardList.objects.filter(board_id=board_id).order_by('position')
    
    def get_serializer_class(self):
        if self.action == 'create':
            return BoardListCreateSerializer
        return BoardListSerializer
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        board_id = self.kwargs.get('board_pk')
        context['board'] = get_object_or_404(Board, id=board_id)
        return context
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        board_list = serializer.save()
        
        # Send notifications to workspace members
        from apps.notifications.services import NotificationService
        board = board_list.board
        workspace = board.workspace
        
        NotificationService.notify_list_created(
            workspace=workspace,
            board=board,
            board_list=board_list,
            creator=request.user
        )
        
        return Response({
            'success': True,
            'data': BoardListSerializer(board_list).data,
            'message': 'List created successfully'
        }, status=status.HTTP_201_CREATED)
    
    def update(self, request, *args, **kwargs):
        """Update a board list."""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        board_list = serializer.save()
        
        # Invalidate cache for immediate display
        CacheManager.invalidate_board_detail(str(board_list.board_id))
        
        return Response(serializer.data)
    
    def destroy(self, request, *args, **kwargs):
        """Delete a board list."""
        board_list = self.get_object()
        board_id = str(board_list.board_id)
        
        board_list.delete()
        
        # Invalidate cache for immediate display
        CacheManager.invalidate_board_detail(board_id)
        
        return Response({
            'success': True,
            'message': 'List deleted successfully'
        }, status=status.HTTP_204_NO_CONTENT)


class CardViewSet(viewsets.ModelViewSet):
    """
    ViewSet for cards within board lists.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = CardSerializer
    
    def get_queryset(self):
        list_id = self.kwargs.get('list_pk')
        return Card.objects.filter(list_id=list_id, is_archived=False).order_by('position')
    
    def get_serializer_class(self):
        if self.action == 'create':
            return CardCreateSerializer
        return CardSerializer
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        list_id = self.kwargs.get('list_pk')
        context['list'] = get_object_or_404(BoardList, id=list_id)
        return context
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        card = serializer.save()
        
        return Response({
            'success': True,
            'data': CardSerializer(card, context={'request': request}).data,
            'message': 'Card created successfully'
        }, status=status.HTTP_201_CREATED)
    
    def update(self, request, *args, **kwargs):
        """Update a card."""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        card = serializer.save()
        
        # Invalidate cache for immediate display
        CacheManager.invalidate_board_cards(str(card.list.board_id), str(card.list.id))
        CacheManager.invalidate_board_detail(str(card.list.board_id))
        
        return Response(serializer.data)
    
    def destroy(self, request, *args, **kwargs):
        """Delete a card."""
        card = self.get_object()
        board_id = str(card.list.board_id)
        list_id = str(card.list.id)
        
        card.delete()
        
        # Invalidate cache for immediate display
        CacheManager.invalidate_board_cards(board_id, list_id)
        CacheManager.invalidate_board_detail(board_id)
        
        return Response({
            'success': True,
            'message': 'Card deleted successfully'
        }, status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=True, methods=['post'])
    def move(self, request, **kwargs):
        """Move a card to a new position or different list."""
        card = self.get_object()
        new_position = request.data.get('position', 0)
        new_list_id = request.data.get('list_id')
        
        old_list = card.list
        
        if new_list_id:
            new_list = get_object_or_404(BoardList, id=new_list_id)
            card.list = new_list
        
        card.position = new_position
        card.save()
        
        # Invalidate cache for both old and new lists for immediate display
        CacheManager.invalidate_board_cards(str(old_list.board_id), str(old_list.id))
        if new_list_id and str(new_list_id) != str(old_list.id):
            CacheManager.invalidate_board_cards(str(card.list.board_id), str(card.list.id))
        CacheManager.invalidate_board_detail(str(card.list.board_id))
        
        return Response({
            'success': True,
            'data': CardSerializer(card, context={'request': request}).data,
            'message': 'Card moved successfully'
        })
    
    @action(detail=True, methods=['post'])
    def archive(self, request, **kwargs):
        """Archive a card."""
        card = self.get_object()
        card.is_archived = True
        card.save()
        
        # Invalidate cache for immediate display
        CacheManager.invalidate_board_cards(str(card.list.board_id), str(card.list.id))
        CacheManager.invalidate_board_detail(str(card.list.board_id))
        
        return Response({
            'success': True,
            'message': 'Card archived successfully'
        })


class CardCommentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for card comments.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = CardCommentSerializer
    
    def get_queryset(self):
        card_id = self.kwargs.get('card_pk')
        return CardComment.objects.filter(card_id=card_id).order_by('created_at')
    
    def get_serializer_class(self):
        if self.action == 'create':
            return CardCommentCreateSerializer
        return CardCommentSerializer
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        card_id = self.kwargs.get('card_pk')
        context['card'] = get_object_or_404(Card, id=card_id)
        return context
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        comment = serializer.save()
        
        # Send notifications
        from apps.notifications.services import NotificationService
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        card = comment.card
        mentioned_users = []
        
        # Get mentioned users if mention_ids were provided
        mention_ids = request.data.get('mention_ids', [])
        if mention_ids:
            mentioned_users = User.objects.filter(id__in=mention_ids)
            comment.mentions.set(mentioned_users)
        
        # Send notifications
        NotificationService.notify_card_comment(
            card=card,
            comment_text=comment.text,
            commenter=request.user,
            mentioned_users=mentioned_users
        )
        
        return Response({
            'success': True,
            'data': CardCommentSerializer(comment, context={'request': request}).data,
            'message': 'Comment created successfully'
        }, status=status.HTTP_201_CREATED)
    
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        
        # Only author can edit
        if instance.author != request.user:
            return Response({
                'success': False,
                'error': {'message': 'Permission denied'}
            }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        comment = serializer.save()
        
        return Response({
            'success': True,
            'data': CardCommentSerializer(comment, context={'request': request}).data,
            'message': 'Comment updated successfully'
        })
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        
        # Only author can delete
        if instance.author != request.user:
            return Response({
                'success': False,
                'error': {'message': 'Permission denied'}
            }, status=status.HTTP_403_FORBIDDEN)
        
        instance.delete()
        
        return Response({
            'success': True,
            'message': 'Comment deleted successfully'
        })
