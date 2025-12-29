from django.contrib import admin
from .models import (
    Workspace, WorkspaceMembership, WorkspaceInvitation,
    Board, BoardMembership, BoardList
)


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'owner', 'is_public', 'created_at']
    list_filter = ['is_public', 'is_deleted', 'created_at']
    search_fields = ['name', 'slug', 'owner__email']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created_at', 'updated_at']


@admin.register(WorkspaceMembership)
class WorkspaceMembershipAdmin(admin.ModelAdmin):
    list_display = ['workspace', 'user', 'role', 'is_active', 'joined_at']
    list_filter = ['role', 'is_active', 'joined_at']
    search_fields = ['workspace__name', 'user__email']


@admin.register(WorkspaceInvitation)
class WorkspaceInvitationAdmin(admin.ModelAdmin):
    list_display = ['workspace', 'email', 'role', 'status', 'expires_at']
    list_filter = ['status', 'role', 'created_at']
    search_fields = ['workspace__name', 'email']


@admin.register(Board)
class BoardAdmin(admin.ModelAdmin):
    list_display = ['name', 'workspace', 'board_type', 'is_private', 'position']
    list_filter = ['board_type', 'is_private', 'is_deleted']
    search_fields = ['name', 'workspace__name']


@admin.register(BoardList)
class BoardListAdmin(admin.ModelAdmin):
    list_display = ['name', 'board', 'position', 'wip_limit']
    list_filter = ['board__workspace']
    search_fields = ['name', 'board__name']
