"""
Pytest fixtures for documents app tests.
"""
import pytest
from apps.core.tests.factories import (
    DocumentFactory, BlockFactory, CommentFactory,
    WorkspaceFactory, UserFactory
)


@pytest.fixture
def document(workspace, user):
    """Create a document."""
    return DocumentFactory(workspace=workspace, created_by=user)


@pytest.fixture
def document_with_blocks(document):
    """Create a document with blocks."""
    BlockFactory.create_batch(5, document=document)
    return document


@pytest.fixture
def comment(document, user):
    """Create a comment on a document."""
    return CommentFactory(document=document, author=user)
