from django.contrib import admin
from mptt.admin import MPTTModelAdmin
from .models import Document, Block, DocumentVersion, DocumentPermission, Comment, Attachment


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ['title', 'workspace', 'created_by', 'last_edited_by', 'current_version', 'created_at']
    list_filter = ['workspace', 'is_template', 'is_locked', 'created_at']
    search_fields = ['title', 'tags']
    readonly_fields = ['current_version', 'created_at', 'updated_at']


@admin.register(Block)
class BlockAdmin(MPTTModelAdmin):
    list_display = ['id', 'document', 'block_type', 'text', 'position', 'level']
    list_filter = ['block_type', 'document']
    search_fields = ['text', 'document__title']
    mptt_level_indent = 20


@admin.register(DocumentVersion)
class DocumentVersionAdmin(admin.ModelAdmin):
    list_display = ['document', 'version_number', 'created_by', 'created_at', 'content_size']
    list_filter = ['created_at']
    readonly_fields = ['created_at']


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['document', 'author', 'is_resolved', 'created_at']
    list_filter = ['is_resolved', 'created_at']
    search_fields = ['text', 'document__title']
