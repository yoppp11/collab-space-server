"""
Root conftest.py for pytest configuration.

This file provides shared fixtures and configuration for all tests.
"""
import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from channels.testing import WebsocketCommunicator
from channels.layers import get_channel_layer
from apps.core.tests.factories import (
    UserFactory, SuperUserFactory, WorkspaceFactory,
    DocumentFactory, BlockFactory, CommentFactory,
    WorkspaceMembershipFactory, BoardFactory, NotificationFactory
)

User = get_user_model()


@pytest.fixture(scope='session')
def django_db_setup():
    """Override default database setup for testing."""
    settings.DATABASES['default'] = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }


@pytest.fixture
def api_client():
    """Provide a Django REST Framework API client."""
    return APIClient()


# User fixtures
@pytest.fixture
def user(db):
    """Create a regular user."""
    return UserFactory()


@pytest.fixture
def admin_user(db):
    """Create an admin/superuser."""
    return SuperUserFactory()


@pytest.fixture
def user_with_password(db):
    """Create a user with a known password."""
    return UserFactory(password='testpass123')


@pytest.fixture
def multiple_users(db):
    """Create multiple users."""
    return UserFactory.create_batch(5)


# Workspace fixtures
@pytest.fixture
def workspace(db, user):
    """Create a workspace owned by user."""
    return WorkspaceFactory(owner=user)


@pytest.fixture
def workspace_with_members(db, workspace):
    """Create a workspace with multiple members."""
    WorkspaceMembershipFactory.create_batch(3, workspace=workspace)
    return workspace


@pytest.fixture
def board(db, workspace):
    """Create a board in a workspace."""
    return BoardFactory(workspace=workspace)


@pytest.fixture
def multiple_workspaces(db, user):
    """Create multiple workspaces."""
    return WorkspaceFactory.create_batch(3, owner=user)


# Document fixtures
@pytest.fixture
def document(db, workspace, user):
    """Create a document."""
    return DocumentFactory(workspace=workspace, created_by=user)


@pytest.fixture
def document_with_blocks(db, document):
    """Create a document with blocks."""
    BlockFactory.create_batch(5, document=document)
    return document


@pytest.fixture
def comment(db, document, user):
    """Create a comment on a document."""
    return CommentFactory(document=document, author=user)


# Notification fixtures
@pytest.fixture
def notification(db, user):
    """Create a notification for a user."""
    return NotificationFactory(recipient=user)


@pytest.fixture
def multiple_notifications(db, user):
    """Create multiple notifications."""
    return NotificationFactory.create_batch(5, recipient=user)


@pytest.fixture
def authenticated_client(api_client, user):
    """Provide an authenticated API client."""
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def admin_client(api_client, admin_user):
    """Provide an admin authenticated API client."""
    api_client.force_authenticate(user=admin_user)
    return api_client


@pytest.fixture
def channel_layer():
    """Provide a channel layer for WebSocket testing."""
    from django.conf import settings
    settings.CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer'
        }
    }
    return get_channel_layer()


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear cache before each test."""
    from django.core.cache import cache
    cache.clear()
    yield
    cache.clear()


@pytest.fixture(autouse=True)
def celery_eager_mode(settings):
    """Run Celery tasks synchronously in tests."""
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True


@pytest.fixture
def mock_redis(mocker):
    """Mock Redis client for testing."""
    mock = mocker.MagicMock()
    mocker.patch('apps.core.utils.get_redis_client', return_value=mock)
    return mock
