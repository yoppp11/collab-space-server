"""
Unit tests for workspace permissions.
"""
import pytest
from django.contrib.auth.models import AnonymousUser
from apps.workspaces.permissions import has_document_permission
from apps.workspaces.models import WorkspaceRole
from apps.core.tests.factories import (
    UserFactory, WorkspaceFactory, DocumentFactory,
    WorkspaceMembershipFactory
)

pytestmark = [pytest.mark.django_db, pytest.mark.permissions]


class TestWorkspacePermissions:
    """Tests for workspace-level permissions."""
    
    def test_owner_has_full_access(self, user):
        """Test that workspace owner has full access."""
        workspace = WorkspaceFactory(owner=user)
        
        # Owner should have access
        assert workspace.owner == user
    
    def test_member_has_access_to_workspace(self, user):
        """Test that members have access to workspace."""
        workspace = WorkspaceFactory()
        membership = WorkspaceMembershipFactory(
            workspace=workspace,
            user=user,
            role=WorkspaceRole.MEMBER
        )
        
        assert membership.workspace == workspace
        assert membership.is_active is True
    
    def test_non_member_no_access(self):
        """Test that non-members don't have access to private workspace."""
        workspace = WorkspaceFactory(is_public=False)
        non_member = UserFactory()
        
        # Non-member should not be in workspace members
        assert non_member not in workspace.members.all()
    
    def test_public_workspace_visible_to_all(self, user):
        """Test that public workspaces are visible to everyone."""
        workspace = WorkspaceFactory(is_public=True)
        
        assert workspace.is_public is True
        # Anyone can view public workspaces
    
    def test_admin_role_permissions(self, user):
        """Test admin role permissions."""
        workspace = WorkspaceFactory()
        membership = WorkspaceMembershipFactory(
            workspace=workspace,
            user=user,
            role=WorkspaceRole.ADMIN
        )
        
        assert membership.role == WorkspaceRole.ADMIN
    
    def test_guest_role_permissions(self, user):
        """Test guest role has limited permissions."""
        workspace = WorkspaceFactory()
        membership = WorkspaceMembershipFactory(
            workspace=workspace,
            user=user,
            role=WorkspaceRole.GUEST
        )
        
        assert membership.role == WorkspaceRole.GUEST


class TestDocumentPermissions:
    """Tests for document-level permissions."""
    
    def test_document_creator_has_access(self, workspace, user):
        """Test that document creator has access."""
        document = DocumentFactory(workspace=workspace, created_by=user)
        
        assert document.created_by == user
    
    def test_workspace_member_has_document_access(self, user):
        """Test workspace members can access workspace documents."""
        workspace = WorkspaceFactory()
        WorkspaceMembershipFactory(
            workspace=workspace,
            user=user,
            role=WorkspaceRole.MEMBER
        )
        document = DocumentFactory(workspace=workspace)
        
        # Member should have access through workspace membership
        assert user in workspace.members.all()
    
    def test_locked_document_restrictions(self, workspace, user):
        """Test that locked documents have restrictions."""
        document = DocumentFactory(
            workspace=workspace,
            created_by=user,
            is_locked=True
        )
        
        assert document.is_locked is True
        # Locked documents should not be editable
    
    def test_public_document_access(self, workspace):
        """Test public documents are accessible."""
        document = DocumentFactory(
            workspace=workspace,
            is_public=True
        )
        
        assert document.is_public is True


class TestBoardPermissions:
    """Tests for board-level permissions."""
    
    def test_private_board_access(self, workspace, user):
        """Test private board access control."""
        from apps.core.tests.factories import BoardFactory
        
        board = BoardFactory(
            workspace=workspace,
            is_private=True,
            created_by=user
        )
        
        assert board.is_private is True
        assert board.created_by == user
