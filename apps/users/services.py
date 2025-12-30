"""
User Services - Business Logic Layer
"""
from typing import Optional
from django.contrib.auth import get_user_model
from django.db import transaction, models
from django.utils import timezone
from .models import UserActivity, UserSession

User = get_user_model()


class UserService:
    """
    Service class for user-related business logic.
    """
    
    @staticmethod
    def log_activity(
        user: User,
        activity_type: str,
        description: str = '',
        metadata: dict = None,
        request=None,
        content_type: str = '',
        object_id: str = None
    ) -> UserActivity:
        """
        Log a user activity.
        """
        ip_address = None
        if request:
            ip_address = UserService.get_client_ip(request)
        
        return UserActivity.objects.create(
            user=user,
            activity_type=activity_type,
            description=description,
            metadata=metadata or {},
            ip_address=ip_address,
            content_type=content_type,
            object_id=object_id
        )
    
    @staticmethod
    def get_client_ip(request) -> Optional[str]:
        """
        Extract client IP from request headers.
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')
    
    @staticmethod
    @transaction.atomic
    def create_or_update_session(
        user: User,
        session_key: str,
        device_info: dict = None,
        ip_address: str = None
    ) -> UserSession:
        """
        Create or update a user session.
        """
        session, created = UserSession.objects.update_or_create(
            user=user,
            session_key=session_key,
            defaults={
                'device_info': device_info or {},
                'ip_address': ip_address,
                'is_active': True,
                'last_activity': timezone.now()
            }
        )
        return session
    
    @staticmethod
    def deactivate_session(session_key: str):
        """
        Deactivate a user session.
        """
        UserSession.objects.filter(session_key=session_key).update(
            is_active=False
        )
    
    @staticmethod
    def get_active_sessions(user: User):
        """
        Get all active sessions for a user.
        """
        return UserSession.objects.filter(
            user=user,
            is_active=True
        ).order_by('-last_activity')
    
    @staticmethod
    def cleanup_expired_sessions(expiry_hours: int = 24):
        """
        Clean up sessions that have been inactive.
        """
        cutoff = timezone.now() - timezone.timedelta(hours=expiry_hours)
        return UserSession.objects.filter(
            last_activity__lt=cutoff
        ).delete()
    
    @staticmethod
    def update_last_seen(user: User):
        """
        Update user's last seen timestamp efficiently.
        """
        User.objects.filter(id=user.id).update(
            last_seen=timezone.now()
        )


class UserSelector:
    """
    Selector class for user queries.
    """
    
    @staticmethod
    def get_by_email(email: str) -> Optional[User]:
        """Get user by email."""
        return User.objects.filter(email__iexact=email).first()
    
    @staticmethod
    def get_by_username(username: str) -> Optional[User]:
        """Get user by username."""
        return User.objects.filter(username__iexact=username).first()
    
    @staticmethod
    def search_users(query: str, limit: int = 10):
        """
        Search users by email, username, or name.
        """
        return User.objects.filter(
            models.Q(email__icontains=query) |
            models.Q(username__icontains=query) |
            models.Q(first_name__icontains=query) |
            models.Q(last_name__icontains=query)
        ).filter(is_active=True)[:limit]
    
    @staticmethod
    def get_online_users(minutes: int = 5):
        """
        Get users who were active in the last N minutes.
        """
        cutoff = timezone.now() - timezone.timedelta(minutes=minutes)
        return User.objects.filter(
            last_seen__gte=cutoff,
            is_active=True
        )
