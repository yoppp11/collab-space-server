"""
Pytest fixtures for users app tests.
"""
import pytest
from django.contrib.auth import get_user_model
from apps.core.tests.factories import UserFactory, SuperUserFactory

User = get_user_model()


@pytest.fixture
def user():
    """Create a regular user."""
    return UserFactory()


@pytest.fixture
def admin_user():
    """Create an admin/superuser."""
    return SuperUserFactory()


@pytest.fixture
def user_with_password():
    """Create a user with a known password."""
    return UserFactory(password='testpass123')


@pytest.fixture
def multiple_users():
    """Create multiple users."""
    return UserFactory.create_batch(5)
