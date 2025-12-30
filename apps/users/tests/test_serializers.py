"""
Unit tests for User serializers.
"""
import pytest
from django.contrib.auth import get_user_model
from apps.users.serializers import (
    UserSerializer, UserPublicSerializer, UserCreateSerializer,
    PasswordChangeSerializer, UserPreferencesSerializer,
    CustomTokenObtainPairSerializer
)
from apps.core.tests.factories import UserFactory

User = get_user_model()

pytestmark = pytest.mark.django_db


class TestUserSerializer:
    """Tests for UserSerializer."""
    
    def test_serialize_user(self):
        """Test serializing a user."""
        user = UserFactory(
            email='test@example.com',
            username='testuser',
            first_name='John',
            last_name='Doe'
        )
        serializer = UserSerializer(user)
        data = serializer.data
        
        assert data['email'] == 'test@example.com'
        assert data['username'] == 'testuser'
        assert data['first_name'] == 'John'
        assert data['last_name'] == 'Doe'
        assert data['full_name'] == 'John Doe'
        assert data['display_name'] == 'testuser'
        assert data['initials'] == 'JD'
        assert 'id' in data
        assert 'created_at' in data
    
    def test_user_serializer_read_only_fields(self):
        """Test that certain fields are read-only."""
        user = UserFactory()
        data = {
            'email': 'newemail@example.com',  # Should be read-only
            'first_name': 'NewName',
        }
        serializer = UserSerializer(user, data=data, partial=True)
        assert serializer.is_valid()
        updated_user = serializer.save()
        
        # Email should not change (read-only)
        assert updated_user.email == user.email
        # First name should change
        assert updated_user.first_name == 'NewName'
    
    def test_update_user_profile(self):
        """Test updating user profile."""
        user = UserFactory()
        data = {
            'first_name': 'Updated',
            'last_name': 'Name',
            'bio': 'New bio',
            'timezone': 'America/New_York',
        }
        serializer = UserSerializer(user, data=data, partial=True)
        assert serializer.is_valid()
        updated_user = serializer.save()
        
        assert updated_user.first_name == 'Updated'
        assert updated_user.last_name == 'Name'
        assert updated_user.bio == 'New bio'
        assert updated_user.timezone == 'America/New_York'


class TestUserPublicSerializer:
    """Tests for UserPublicSerializer."""
    
    def test_serialize_public_user(self):
        """Test serializing a user with public serializer."""
        user = UserFactory(
            username='johndoe',
            first_name='John',
            last_name='Doe'
        )
        serializer = UserPublicSerializer(user)
        data = serializer.data
        
        assert data['username'] == 'johndoe'
        assert data['full_name'] == 'John Doe'
        assert data['display_name'] == 'johndoe'
        assert 'id' in data
        assert 'avatar' in data
        # Email should not be in public serializer
        assert 'email' not in data
        assert 'timezone' not in data
        assert 'preferences' not in data


class TestUserCreateSerializer:
    """Tests for UserCreateSerializer."""
    
    def test_create_user(self):
        """Test creating a user with serializer."""
        data = {
            'email': 'newuser@example.com',
            'password': 'StrongPass123!',
            'password_confirm': 'StrongPass123!',
            'first_name': 'John',
            'last_name': 'Doe',
            'username': 'johndoe',
        }
        serializer = UserCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        user = serializer.save()
        
        assert user.email == 'newuser@example.com'
        assert user.check_password('StrongPass123!')
        assert user.first_name == 'John'
        assert user.last_name == 'Doe'
        assert user.username == 'johndoe'
    
    def test_password_mismatch(self):
        """Test that mismatched passwords raise validation error."""
        data = {
            'email': 'test@example.com',
            'password': 'StrongPass123!',
            'password_confirm': 'DifferentPass123!',
        }
        serializer = UserCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert 'password_confirm' in serializer.errors
    
    def test_duplicate_email(self):
        """Test that duplicate email raises validation error."""
        UserFactory(email='existing@example.com')
        data = {
            'email': 'existing@example.com',
            'password': 'StrongPass123!',
            'password_confirm': 'StrongPass123!',
        }
        serializer = UserCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert 'email' in serializer.errors
    
    def test_weak_password_validation(self):
        """Test that weak passwords are rejected."""
        data = {
            'email': 'test@example.com',
            'password': '123',  # Too weak
            'password_confirm': '123',
        }
        serializer = UserCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert 'password' in serializer.errors


class TestPasswordChangeSerializer:
    """Tests for PasswordChangeSerializer."""
    
    def test_change_password_success(self, user_with_password):
        """Test successfully changing password."""
        data = {
            'old_password': 'testpass123',
            'new_password': 'NewStrongPass123!',
            'new_password_confirm': 'NewStrongPass123!',
        }
        serializer = PasswordChangeSerializer(
            data=data,
            context={'request': type('obj', (object,), {'user': user_with_password})()}
        )
        assert serializer.is_valid(), serializer.errors
    
    def test_wrong_old_password(self, user_with_password):
        """Test that wrong old password is rejected."""
        data = {
            'old_password': 'wrongpass',
            'new_password': 'NewStrongPass123!',
            'new_password_confirm': 'NewStrongPass123!',
        }
        serializer = PasswordChangeSerializer(
            data=data,
            context={'request': type('obj', (object,), {'user': user_with_password})()}
        )
        assert not serializer.is_valid()
        assert 'old_password' in serializer.errors
    
    def test_new_password_mismatch(self, user_with_password):
        """Test that mismatched new passwords are rejected."""
        data = {
            'old_password': 'testpass123',
            'new_password': 'NewStrongPass123!',
            'new_password_confirm': 'DifferentPass123!',
        }
        serializer = PasswordChangeSerializer(
            data=data,
            context={'request': type('obj', (object,), {'user': user_with_password})()}
        )
        assert not serializer.is_valid()
        assert 'new_password_confirm' in serializer.errors


class TestUserPreferencesSerializer:
    """Tests for UserPreferencesSerializer."""
    
    def test_update_preferences(self, user):
        """Test updating user preferences."""
        data = {
            'theme': 'dark',
            'notification_email': False,
        }
        serializer = UserPreferencesSerializer(user, data=data, partial=True)
        assert serializer.is_valid(), serializer.errors
        updated_user = serializer.save()
        
        assert updated_user.preferences['theme'] == 'dark'
        assert updated_user.preferences['notification_email'] is False
