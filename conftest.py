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
