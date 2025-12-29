"""
Document Signals
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import Document, Block
from django.utils import timezone


@receiver(post_save, sender=Block)
def block_saved(sender, instance, created, **kwargs):
    """
    Update document's last_edited timestamp when a block is modified.
    """
    Document.objects.filter(id=instance.document_id).update(
        last_edited_at=timezone.now(),
        last_edited_by=instance.last_edited_by
    )


@receiver(pre_save, sender=Block)
def block_pre_save(sender, instance, **kwargs):
    """
    Increment version on block updates.
    """
    if instance.pk:  # Existing block
        instance.version += 1
