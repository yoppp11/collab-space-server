"""
Pytest fixtures for collaboration app tests.

Note: Common fixtures (user, document, etc.) are defined in the root conftest.py
and are available to all tests.
"""
import pytest
from channels.testing import WebsocketCommunicator
from apps.collaboration.consumers import DocumentConsumer


@pytest.fixture
def websocket_communicator(db, user, document):
    """Create a WebSocket communicator for testing."""
    communicator = WebsocketCommunicator(
        DocumentConsumer.as_asgi(),
        f"/ws/documents/{document.id}/"
    )
    communicator.scope['user'] = user
    return communicator
