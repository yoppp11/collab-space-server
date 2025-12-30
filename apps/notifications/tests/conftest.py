"""
Pytest fixtures for notifications app tests.
"""
import pytest
from apps.core.tests.factories import NotificationFactory


@pytest.fixture
def notification(user):
    """Create a notification for a user."""
    return NotificationFactory(recipient=user)


@pytest.fixture
def multiple_notifications(user):
    """Create multiple notifications."""
    return NotificationFactory.create_batch(5, recipient=user)
