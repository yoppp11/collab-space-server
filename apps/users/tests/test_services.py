"""
Unit tests for User services.
"""
import pytest
from django.utils import timezone
from apps.users.services import UserService
from apps.users.models import UserActivity, UserSession
from apps.core.tests.factories import UserFactory, UserSessionFactory

pytestmark = pytest.mark.django_db


class TestUserService:
    """Tests for UserService."""
    
    def test_log_activity(self, user):
        """Test logging user activity."""
        activity = UserService.log_activity(
            user=user,
            activity_type='login',
            description='User logged in',
            metadata={'device': 'desktop'}
        )
        
        assert activity.user == user
        assert activity.activity_type == 'login'
        assert activity.description == 'User logged in'
        assert activity.metadata == {'device': 'desktop'}
    
    def test_log_activity_with_request(self, user, rf):
        """Test logging activity with request object."""
        request = rf.get('/')
        request.META['REMOTE_ADDR'] = '192.168.1.1'
        
        activity = UserService.log_activity(
            user=user,
            activity_type='login',
            request=request
        )
        
        assert activity.ip_address == '192.168.1.1'
    
    def test_get_client_ip_from_remote_addr(self, rf):
        """Test getting client IP from REMOTE_ADDR."""
        request = rf.get('/')
        request.META['REMOTE_ADDR'] = '192.168.1.100'
        
        ip = UserService.get_client_ip(request)
        assert ip == '192.168.1.100'
    
    def test_get_client_ip_from_x_forwarded_for(self, rf):
        """Test getting client IP from X-Forwarded-For header."""
        request = rf.get('/')
        request.META['HTTP_X_FORWARDED_FOR'] = '10.0.0.1, 192.168.1.1'
        
        ip = UserService.get_client_ip(request)
        assert ip == '10.0.0.1'
    
    def test_create_session(self, user):
        """Test creating a user session."""
        session = UserService.create_or_update_session(
            user=user,
            session_key='test-session-key',
            device_info={'browser': 'Chrome'},
            ip_address='192.168.1.1'
        )
        
        assert session.user == user
        assert session.session_key == 'test-session-key'
        assert session.device_info == {'browser': 'Chrome'}
        assert session.ip_address == '192.168.1.1'
        assert session.is_active is True
    
    def test_update_existing_session(self, user):
        """Test updating an existing session."""
        # Create initial session
        session1 = UserService.create_or_update_session(
            user=user,
            session_key='test-session',
            device_info={'browser': 'Chrome'}
        )
        
        # Update the same session
        session2 = UserService.create_or_update_session(
            user=user,
            session_key='test-session',
            device_info={'browser': 'Firefox'}
        )
        
        assert session1.id == session2.id
        assert session2.device_info == {'browser': 'Firefox'}
    
    def test_deactivate_session(self, user):
        """Test deactivating a session."""
        session = UserSessionFactory(user=user, session_key='test-key')
        assert session.is_active is True
        
        UserService.deactivate_session('test-key')
        
        session.refresh_from_db()
        assert session.is_active is False
    
    def test_get_active_sessions(self, user):
        """Test getting active sessions for a user."""
        # Create active and inactive sessions
        active1 = UserSessionFactory(user=user, is_active=True)
        active2 = UserSessionFactory(user=user, is_active=True)
        inactive = UserSessionFactory(user=user, is_active=False)
        
        sessions = UserService.get_active_sessions(user)
        
        assert sessions.count() == 2
        assert active1 in sessions
        assert active2 in sessions
        assert inactive not in sessions


@pytest.fixture
def rf():
    """Provide a RequestFactory."""
    from django.test import RequestFactory
    return RequestFactory()
