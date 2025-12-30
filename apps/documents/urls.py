"""
Document URL Configuration
"""
from django.urls import path, include
from rest_framework_nested import routers
from .views import DocumentViewSet, BlockViewSet, CommentViewSet

app_name = 'documents'

router = routers.DefaultRouter()
router.register(r'', DocumentViewSet, basename='document')
router.register(r'blocks', BlockViewSet, basename='block')
router.register(r'comments', CommentViewSet, basename='comment')

# Nested routes for blocks within documents
documents_router = routers.NestedDefaultRouter(router, r'', lookup='document')
documents_router.register(r'blocks', BlockViewSet, basename='document-blocks')
documents_router.register(r'comments', CommentViewSet, basename='document-comments')

urlpatterns = [
    path('', include(router.urls)),
    path('', include(documents_router.urls)),
]
