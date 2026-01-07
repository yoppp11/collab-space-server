"""
Unit tests for Core views.
"""
import pytest
from unittest.mock import patch, MagicMock
from django.urls import reverse
from rest_framework import status
from apps.core.tests.factories import UserFactory, SuperUserFactory

pytestmark = pytest.mark.django_db


class TestCacheStatsView:
    """Tests for cache_stats view."""
    
    @patch('apps.core.views.get_cache_stats')
    def test_admin_can_view_cache_stats(self, mock_get_stats, admin_client):
        """Test that admin can view cache statistics."""
        mock_get_stats.return_value = {
            'keys': 100,
            'memory_used': '1MB',
            'hits': 500,
            'misses': 50
        }
        
        url = reverse('core:cache-stats')
        response = admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True
        assert 'data' in response.data
    
    def test_non_admin_cannot_view_cache_stats(self, authenticated_client):
        """Test that non-admin cannot view cache statistics."""
        url = reverse('core:cache-stats')
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_unauthenticated_cannot_view_cache_stats(self, api_client):
        """Test that unauthenticated users cannot view cache statistics."""
        url = reverse('core:cache-stats')
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestClearCacheView:
    """Tests for clear_cache view."""
    
    @patch('apps.core.views.clear_all_cache')
    def test_admin_can_clear_all_cache(self, mock_clear, admin_client):
        """Test that admin can clear all cache."""
        url = reverse('core:cache-clear')
        response = admin_client.post(url, {'type': 'all'}, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True
        mock_clear.assert_called_once()
    
    @patch('apps.core.views.CacheManager')
    def test_admin_can_clear_user_cache(self, mock_manager, admin_client):
        """Test that admin can clear specific user's cache."""
        url = reverse('core:cache-clear')
        response = admin_client.post(
            url, 
            {'type': 'user', 'user_id': '123'}, 
            format='json'
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True
        mock_manager.invalidate_user_all.assert_called_with('123')
    
    def test_clear_user_cache_requires_user_id(self, admin_client):
        """Test that clearing user cache requires user_id."""
        url = reverse('core:cache-clear')
        response = admin_client.post(url, {'type': 'user'}, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    @patch('apps.core.views.CacheManager')
    def test_admin_can_clear_workspace_cache(self, mock_manager, admin_client):
        """Test that admin can clear specific workspace's cache."""
        url = reverse('core:cache-clear')
        response = admin_client.post(
            url, 
            {'type': 'workspace', 'workspace_id': '456'}, 
            format='json'
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True
        mock_manager.invalidate_workspace_all.assert_called_with('456')
    
    def test_clear_workspace_cache_requires_workspace_id(self, admin_client):
        """Test that clearing workspace cache requires workspace_id."""
        url = reverse('core:cache-clear')
        response = admin_client.post(url, {'type': 'workspace'}, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_invalid_cache_type_returns_error(self, admin_client):
        """Test that invalid cache type returns error."""
        url = reverse('core:cache-clear')
        response = admin_client.post(url, {'type': 'invalid'}, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_non_admin_cannot_clear_cache(self, authenticated_client):
        """Test that non-admin cannot clear cache."""
        url = reverse('core:cache-clear')
        response = authenticated_client.post(url, {'type': 'all'}, format='json')
        
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestInvalidateMyCacheView:
    """Tests for invalidate_my_cache view."""
    
    @patch('apps.core.views.CacheManager')
    def test_user_can_invalidate_own_cache(self, mock_manager, authenticated_client, user):
        """Test that user can invalidate their own cache."""
        url = reverse('core:cache-invalidate-mine')
        response = authenticated_client.post(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True
        mock_manager.invalidate_user_all.assert_called_with(str(user.id))
    
    def test_unauthenticated_cannot_invalidate_cache(self, api_client):
        """Test that unauthenticated users cannot invalidate cache."""
        url = reverse('core:cache-invalidate-mine')
        response = api_client.post(url)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
