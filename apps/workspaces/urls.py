"""
Workspace URL Configuration
"""
from django.urls import path, include
from rest_framework_nested import routers

from .views import (
    WorkspaceViewSet, BoardViewSet, BoardListViewSet, CardViewSet,
    InvitationAcceptView, JoinWorkspaceByCodeView, CardCommentViewSet
)

app_name = 'workspaces'

router = routers.DefaultRouter()
router.register(r'', WorkspaceViewSet, basename='workspace')

# Nested routes for boards within workspaces
workspaces_router = routers.NestedDefaultRouter(router, r'', lookup='workspace')
workspaces_router.register(r'boards', BoardViewSet, basename='workspace-boards')

# Nested routes for lists within boards
boards_router = routers.NestedDefaultRouter(workspaces_router, r'boards', lookup='board')
boards_router.register(r'lists', BoardListViewSet, basename='board-lists')

# Nested routes for cards within lists
lists_router = routers.NestedDefaultRouter(boards_router, r'lists', lookup='list')
lists_router.register(r'cards', CardViewSet, basename='list-cards')

# Nested routes for comments within cards
cards_router = routers.NestedDefaultRouter(lists_router, r'cards', lookup='card')
cards_router.register(r'comments', CardCommentViewSet, basename='card-comments')

urlpatterns = [
    # Custom endpoints before router to avoid conflicts
    path('join/', JoinWorkspaceByCodeView.as_view(), name='join-by-code'),
    path('invitations/<str:token>/accept/', InvitationAcceptView.as_view(), name='invitation-accept'),
    
    # Router endpoints
    path('', include(router.urls)),
    path('', include(workspaces_router.urls)),
    path('', include(boards_router.urls)),
    path('', include(lists_router.urls)),
    path('', include(cards_router.urls)),
    path('boards/', include((workspaces_router.urls, 'boards'))),
]
