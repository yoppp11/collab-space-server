"""
Workspace Permission Classes

Implements granular RBAC at workspace, board, and document levels.
"""
from rest_framework import permissions
from django.core.cache import cache
from .models import WorkspaceMembership, BoardMembership, WorkspaceRole, DocumentRole


class RolePermissions:
    """
    Define what each role can do.
    """
    
    # Workspace-level permissions
    WORKSPACE_PERMISSIONS = {
        WorkspaceRole.OWNER: {
            'can_manage_workspace',
            'can_delete_workspace',
            'can_manage_members',
            'can_manage_roles',
            'can_create_boards',
            'can_delete_boards',
            'can_view_analytics',
            'can_export_data',
            'can_manage_billing',
        },
        WorkspaceRole.ADMIN: {
            'can_manage_workspace',
            'can_manage_members',
            'can_create_boards',
            'can_delete_boards',
            'can_view_analytics',
            'can_export_data',
        },
        WorkspaceRole.MEMBER: {
            'can_create_boards',
            'can_view_analytics',
        },
        WorkspaceRole.GUEST: set(),
    }
    
    # Document-level permissions
    DOCUMENT_PERMISSIONS = {
        DocumentRole.OWNER: {
            'can_edit',
            'can_delete',
            'can_share',
            'can_manage_permissions',
            'can_comment',
            'can_view',
            'can_export',
            'can_move',
        },
        DocumentRole.EDITOR: {
            'can_edit',
            'can_comment',
            'can_view',
            'can_export',
        },
        DocumentRole.COMMENTER: {
            'can_comment',
            'can_view',
        },
        DocumentRole.VIEWER: {
            'can_view',
        },
    }


def get_workspace_role(user, workspace):
    """
    Get user's role in a workspace with caching.
    """
    if not user.is_authenticated:
        return None
    
    cache_key = f"ws_role:{workspace.id}:{user.id}"
    role = cache.get(cache_key)
    
    if role is None:
        membership = WorkspaceMembership.objects.filter(
            workspace=workspace,
            user=user,
            is_active=True
        ).first()
        
        role = membership.role if membership else None
        cache.set(cache_key, role, timeout=300)  # Cache for 5 minutes
    
    return role


def get_document_role(user, document):
    """
    Get user's effective role for a document.
    Considers workspace role and document-specific permissions.
    """
    if not user.is_authenticated:
        return None
    
    cache_key = f"doc_role:{document.id}:{user.id}"
    role = cache.get(cache_key)
    
    if role is None:
        # Check if user is document owner
        if document.created_by_id == user.id:
            role = DocumentRole.OWNER
        else:
            # Check document-specific permission
            from apps.documents.models import DocumentPermission
            doc_perm = DocumentPermission.objects.filter(
                document=document,
                user=user
            ).first()
            
            if doc_perm:
                role = doc_perm.role
            else:
                # Fall back to workspace role mapping
                ws_role = get_workspace_role(user, document.workspace)
                role = map_workspace_to_document_role(ws_role)
        
        cache.set(cache_key, role, timeout=300)
    
    return role


def map_workspace_to_document_role(workspace_role):
    """
    Map workspace role to default document permissions.
    """
    mapping = {
        WorkspaceRole.OWNER: DocumentRole.OWNER,
        WorkspaceRole.ADMIN: DocumentRole.EDITOR,
        WorkspaceRole.MEMBER: DocumentRole.EDITOR,
        WorkspaceRole.GUEST: DocumentRole.VIEWER,
    }
    return mapping.get(workspace_role)


def has_workspace_permission(user, workspace, permission):
    """
    Check if user has a specific workspace permission.
    """
    role = get_workspace_role(user, workspace)
    if not role:
        return False
    
    return permission in RolePermissions.WORKSPACE_PERMISSIONS.get(role, set())


def has_document_permission(user, document, permission):
    """
    Check if user has a specific document permission.
    """
    role = get_document_role(user, document)
    if not role:
        return False
    
    return permission in RolePermissions.DOCUMENT_PERMISSIONS.get(role, set())


def invalidate_permission_cache(user_id, workspace_id=None, document_id=None):
    """
    Invalidate permission cache when roles change.
    """
    if workspace_id:
        cache.delete(f"ws_role:{workspace_id}:{user_id}")
    if document_id:
        cache.delete(f"doc_role:{document_id}:{user_id}")


# =============================================================================
# DRF Permission Classes
# =============================================================================

class IsWorkspaceMember(permissions.BasePermission):
    """
    Check if user is a member of the workspace.
    """
    
    def has_object_permission(self, request, view, obj):
        # Get workspace from object
        workspace = getattr(obj, 'workspace', obj)
        role = get_workspace_role(request.user, workspace)
        return role is not None


class IsWorkspaceAdmin(permissions.BasePermission):
    """
    Check if user is admin or owner of workspace.
    """
    
    def has_object_permission(self, request, view, obj):
        workspace = getattr(obj, 'workspace', obj)
        role = get_workspace_role(request.user, workspace)
        return role in [WorkspaceRole.OWNER, WorkspaceRole.ADMIN]


class IsWorkspaceOwner(permissions.BasePermission):
    """
    Check if user is the owner of the workspace.
    """
    
    def has_object_permission(self, request, view, obj):
        workspace = getattr(obj, 'workspace', obj)
        role = get_workspace_role(request.user, workspace)
        return role == WorkspaceRole.OWNER


class CanEditDocument(permissions.BasePermission):
    """
    Check if user can edit the document.
    """
    
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return has_document_permission(request.user, obj, 'can_view')
        return has_document_permission(request.user, obj, 'can_edit')


class CanViewDocument(permissions.BasePermission):
    """
    Check if user can view the document.
    """
    
    def has_object_permission(self, request, view, obj):
        return has_document_permission(request.user, obj, 'can_view')


class CanManageDocumentPermissions(permissions.BasePermission):
    """
    Check if user can manage document permissions.
    """
    
    def has_object_permission(self, request, view, obj):
        return has_document_permission(request.user, obj, 'can_manage_permissions')
