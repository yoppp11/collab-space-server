"""
Unit tests for Notification models.
"""
import pytest
from apps.notifications.models import Notification
from apps.core.tests.factories import NotificationFactory, UserFactory

pytestmark = pytest.mark.django_db


class TestNotificationModel:
    """Tests for the Notification model."""
    
    def test_create_notification(self, user):
        """Test creating a notification."""
        notification = NotificationFactory(
            recipient=user,
            notification_type='mention',
            title='You were mentioned',
            message='Someone mentioned you in a comment'
        )
        
        assert notification.recipient == user
        assert notification.notification_type == 'mention'
        assert notification.is_read is False
    
    def test_mark_notification_as_read(self, user):
        """Test marking a notification as read."""
        notification = NotificationFactory(recipient=user, is_read=False)
        
        notification.is_read = True
        notification.save()
        
        notification.refresh_from_db()
        assert notification.is_read is True
    
    def test_unread_notifications_count(self, user):
        """Test counting unread notifications."""
        NotificationFactory.create_batch(3, recipient=user, is_read=False)
        NotificationFactory.create_batch(2, recipient=user, is_read=True)
        
        unread_count = Notification.objects.filter(
            recipient=user,
            is_read=False
        ).count()
        
        assert unread_count == 3
    
    def test_notification_types(self, user):
        """Test different notification types."""
        types = ['mention', 'comment', 'share', 'invite']
        for notif_type in types:
            notification = NotificationFactory(
                recipient=user,
                notification_type=notif_type
            )
            assert notification.notification_type == notif_type
