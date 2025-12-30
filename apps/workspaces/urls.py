"""
Workspace URL Configuration
"""
from django.urls import path, include
from rest_framework_nested import routers

from .views import (
    WorkspaceViewSet, BoardViewSet, BoardListViewSet,
    InvitationAcceptView
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

urlpatterns = [
    path('', include(router.urls)),
    path('', include(workspaces_router.urls)),
    path('', include(boards_router.urls)),
    path('boards/', include((workspaces_router.urls, 'boards'))),
    path('invitations/<str:token>/accept/', InvitationAcceptView.as_view(), name='invitation-accept'),
]
