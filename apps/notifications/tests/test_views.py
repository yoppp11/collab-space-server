"""
Unit tests for Notification views.
"""
import pytest
from django.urls import reverse
from rest_framework import status
from apps.notifications.models import Notification
from apps.core.tests.factories import NotificationFactory, UserFactory

pytestmark = pytest.mark.django_db


class TestNotificationViewSet:
    """Tests for NotificationViewSet."""
    
    def test_list_notifications(self, authenticated_client, user):
        """Test listing user's notifications."""
        NotificationFactory.create_batch(3, recipient=user)
        
        # Create notifications for another user (should not appear)
        other_user = UserFactory()
        NotificationFactory.create_batch(2, recipient=other_user)
        
        url = reverse('notifications:notification-list')
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_retrieve_notification_marks_as_read(self, authenticated_client, user):
        """Test retrieving a notification marks it as read."""
        notification = NotificationFactory(recipient=user, is_read=False)
        
        url = reverse('notifications:notification-detail', args=[notification.id])
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True
        
        # Verify notification is now marked as read
        notification.refresh_from_db()
        assert notification.is_read is True
        assert notification.read_at is not None
    
    def test_retrieve_already_read_notification(self, authenticated_client, user):
        """Test retrieving an already read notification."""
        from django.utils import timezone
        read_time = timezone.now()
        notification = NotificationFactory(
            recipient=user, 
            is_read=True, 
            read_at=read_time
        )
        
        url = reverse('notifications:notification-detail', args=[notification.id])
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        
        notification.refresh_from_db()
        assert notification.is_read is True
    
    def test_unread_count(self, authenticated_client, user):
        """Test getting unread notification count."""
        NotificationFactory.create_batch(3, recipient=user, is_read=False)
        NotificationFactory.create_batch(2, recipient=user, is_read=True)
        
        url = reverse('notifications:notification-unread-count')
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True
        assert response.data['data']['count'] == 3
    
    def test_mark_read(self, authenticated_client, user):
        """Test marking a notification as read."""
        notification = NotificationFactory(recipient=user, is_read=False)
        
        url = reverse('notifications:notification-mark-read', args=[notification.id])
        response = authenticated_client.post(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True
        
        notification.refresh_from_db()
        assert notification.is_read is True
        assert notification.read_at is not None
    
    def test_mark_all_read(self, authenticated_client, user):
        """Test marking all notifications as read."""
        NotificationFactory.create_batch(5, recipient=user, is_read=False)
        
        url = reverse('notifications:notification-mark-all-read')
        response = authenticated_client.post(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True
        
        # Verify all are now read
        unread_count = Notification.objects.filter(
            recipient=user,
            is_read=False
        ).count()
        assert unread_count == 0
    
    def test_unauthenticated_access(self, api_client):
        """Test that unauthenticated users cannot access notifications."""
        url = reverse('notifications:notification-list')
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_cannot_access_other_users_notifications(self, authenticated_client, user):
        """Test that users cannot access other users' notifications."""
        other_user = UserFactory()
        notification = NotificationFactory(recipient=other_user)
        
        url = reverse('notifications:notification-detail', args=[notification.id])
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
