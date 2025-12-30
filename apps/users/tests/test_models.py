"""
Unit tests for User models.
"""
import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from apps.core.tests.factories import UserFactory, UserSessionFactory, UserActivityFactory

User = get_user_model()

pytestmark = pytest.mark.django_db


class TestUserModel:
    """Tests for the User model."""
    
    def test_create_user_with_email(self):
        """Test creating a user with email."""
        user = UserFactory(email='test@example.com')
        assert user.email == 'test@example.com'
        assert user.is_active is True
        assert user.is_staff is False
        assert user.is_superuser is False
    
    def test_create_user_with_password(self):
        """Test creating a user with password."""
        user = UserFactory()
        user.set_password('testpass123')
        user.save()
        assert user.check_password('testpass123')
    
    def test_user_email_must_be_unique(self):
        """Test that user email must be unique."""
        UserFactory(email='test@example.com')
        with pytest.raises(IntegrityError):
            UserFactory(email='test@example.com')
    
    def test_user_str_representation(self):
        """Test user string representation."""
        user = UserFactory(email='test@example.com')
        assert str(user) == 'test@example.com'
    
    def test_user_full_name_property(self):
        """Test user full_name property."""
        user = UserFactory(first_name='John', last_name='Doe')
        assert user.full_name == 'John Doe'
    
    def test_user_full_name_fallback_to_email(self):
        """Test full_name falls back to email username when names are empty."""
        user = UserFactory(email='john@example.com', first_name='', last_name='')
        assert user.full_name == 'john'
    
    def test_user_display_name_with_username(self):
        """Test display_name returns username if available."""
        user = UserFactory(username='johndoe')
        assert user.display_name == 'johndoe'
    
    def test_user_display_name_fallback(self):
        """Test display_name falls back to full_name."""
        user = UserFactory(username='', first_name='John', last_name='Doe')
        assert user.display_name == 'John Doe'
    
    def test_user_initials(self):
        """Test user initials property."""
        user = UserFactory(first_name='John', last_name='Doe')
        assert user.initials == 'JD'
    
    def test_user_initials_from_email(self):
        """Test initials fall back to email when no names."""
        user = UserFactory(email='test@example.com', first_name='', last_name='')
        assert len(user.initials) == 2
        assert user.initials.isupper()
    
    def test_create_superuser(self):
        """Test creating a superuser."""
        user = User.objects.create_superuser(
            email='admin@example.com',
            password='adminpass123'
        )
        assert user.is_staff is True
        assert user.is_superuser is True
        assert user.is_active is True
        assert user.is_verified is True
    
    def test_user_manager_requires_email(self):
        """Test that creating user without email raises error."""
        with pytest.raises(ValueError, match='Users must have an email address'):
            User.objects.create_user(email='', password='testpass')
    
    def test_user_preferences_default(self):
        """Test user preferences default to empty dict."""
        user = UserFactory()
        assert user.preferences == {}
    
    def test_user_avatar_color_default(self):
        """Test user avatar_color has default value."""
        user = UserFactory()
        assert user.avatar_color.startswith('#')


class TestUserSessionModel:
    """Tests for the UserSession model."""
    
    def test_create_user_session(self):
        """Test creating a user session."""
        session = UserSessionFactory()
        assert session.user is not None
        assert session.session_key is not None
        assert session.is_active is True
    
    def test_user_session_str_representation(self):
        """Test user session string representation."""
        session = UserSessionFactory()
        assert session.user.email in str(session)
        assert session.session_key[:8] in str(session)
    
    def test_user_has_multiple_sessions(self):
        """Test that a user can have multiple sessions."""
        user = UserFactory()
        session1 = UserSessionFactory(user=user)
        session2 = UserSessionFactory(user=user)
        assert user.sessions.count() == 2
        assert session1 in user.sessions.all()
        assert session2 in user.sessions.all()


class TestUserActivityModel:
    """Tests for the UserActivity model."""
    
    def test_create_user_activity(self):
        """Test creating a user activity."""
        activity = UserActivityFactory()
        assert activity.user is not None
        assert activity.activity_type in dict(activity.ActivityType.choices)
    
    def test_user_activity_str_representation(self):
        """Test user activity string representation."""
        activity = UserActivityFactory(activity_type='login')
        assert activity.user.email in str(activity)
        assert 'login' in str(activity)
    
    def test_user_has_multiple_activities(self):
        """Test that a user can have multiple activities."""
        user = UserFactory()
        UserActivityFactory(user=user, activity_type='login')
        UserActivityFactory(user=user, activity_type='profile_update')
        assert user.activities.count() == 2
    
    def test_activity_ordering(self):
        """Test that activities are ordered by created_at desc."""
        user = UserFactory()
        activity1 = UserActivityFactory(user=user)
        activity2 = UserActivityFactory(user=user)
        activities = user.activities.all()
        assert activities[0] == activity2  # Most recent first
        assert activities[1] == activity1
    
    def test_activity_metadata_default(self):
        """Test activity metadata defaults to empty dict."""
        activity = UserActivityFactory()
        assert activity.metadata == {}
