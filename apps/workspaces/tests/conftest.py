"""
Pytest fixtures for workspaces app tests.
"""
import pytest
from apps.core.tests.factories import (
    WorkspaceFactory, WorkspaceMembershipFactory,
    BoardFactory, UserFactory
)


@pytest.fixture
def workspace(user):
    """Create a workspace owned by user."""
    return WorkspaceFactory(owner=user)


@pytest.fixture
def workspace_with_members(workspace):
    """Create a workspace with multiple members."""
    WorkspaceMembershipFactory.create_batch(3, workspace=workspace)
    return workspace


@pytest.fixture
def board(workspace):
    """Create a board in a workspace."""
    return BoardFactory(workspace=workspace)


@pytest.fixture
def multiple_workspaces(user):
    """Create multiple workspaces."""
    return WorkspaceFactory.create_batch(3, owner=user)
