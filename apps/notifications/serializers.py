"""
Notification Serializers
"""
from rest_framework import serializers
from .models import Notification
from apps.users.serializers import UserPublicSerializer


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for notifications."""
    actor = UserPublicSerializer(read_only=True)
    
    class Meta:
        model = Notification
        fields = [
            'id', 'notification_type', 'actor', 'title', 'message',
            'action_url', 'is_read', 'read_at', 'metadata', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
