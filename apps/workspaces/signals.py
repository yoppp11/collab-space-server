"""
Workspace Signals
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import WorkspaceMembership
from .permissions import invalidate_permission_cache


@receiver(post_save, sender=WorkspaceMembership)
def membership_saved(sender, instance, created, **kwargs):
    """
    Invalidate permission cache when membership changes.
    """
    invalidate_permission_cache(
        user_id=instance.user_id,
        workspace_id=instance.workspace_id
    )


@receiver(post_delete, sender=WorkspaceMembership)
def membership_deleted(sender, instance, **kwargs):
    """
    Invalidate permission cache when membership is deleted.
    """
    invalidate_permission_cache(
        user_id=instance.user_id,
        workspace_id=instance.workspace_id
    )
