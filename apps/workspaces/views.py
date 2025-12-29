"""
Workspace API Views
"""
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from .models import (
    Workspace, WorkspaceMembership, WorkspaceInvitation,
    Board, BoardList
)
from .serializers import (
    WorkspaceSerializer, WorkspaceCreateSerializer,
    WorkspaceMembershipSerializer, WorkspaceInvitationSerializer,
    InviteMemberSerializer, BoardSerializer, BoardCreateSerializer,
    BoardListSerializer, BoardListCreateSerializer
)
from .services import WorkspaceService, BoardService, WorkspaceSelector
from .permissions import (
    IsWorkspaceMember, IsWorkspaceAdmin, IsWorkspaceOwner,
    get_workspace_role
)


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
                email=serializer.validated_data['email'],
                role=serializer.validated_data['role'],
                invited_by=request.user,
                message=serializer.validated_data.get('message', '')
            )
            
            # TODO: Send invitation email via Celery task
            
            return Response({
                'success': True,
                'data': WorkspaceInvitationSerializer(invitation).data,
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
        
        return Response({
            'success': True,
            'data': BoardSerializer(board, context={'request': request}).data,
            'message': 'Board created successfully'
        }, status=status.HTTP_201_CREATED)
    
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
