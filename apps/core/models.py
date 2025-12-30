"""
Core Abstract Models for the Collaboration Platform

These models provide common fields and functionality
that are inherited by other models throughout the application.
"""
import uuid
from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    """
    Abstract base model that provides self-updating
    `created_at` and `updated_at` fields.
    """
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        abstract = True
        ordering = ['-created_at']


class UUIDModel(models.Model):
    """
    Abstract base model that uses UUID as primary key
    for better distributed system compatibility.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    class Meta:
        abstract = True


class BaseModel(UUIDModel, TimeStampedModel):
    """
    Combined base model with UUID primary key and timestamps.
    Most models in the application should inherit from this.
    """
    class Meta:
        abstract = True


class SoftDeleteModel(models.Model):
    """
    Abstract model that implements soft delete functionality.
    Records are not actually deleted but marked as deleted.
    """
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False):
        """Override delete to perform soft delete by default."""
        self.soft_delete()

    def hard_delete(self, using=None, keep_parents=False):
        """Actually delete the record from the database."""
        super().delete(using=using, keep_parents=keep_parents)

    def soft_delete(self):
        """Mark the record as deleted."""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=['is_deleted', 'deleted_at'])

    def restore(self):
        """Restore a soft-deleted record."""
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=['is_deleted', 'deleted_at'])


class SoftDeleteManager(models.Manager):
    """Manager that excludes soft-deleted objects by default."""
    
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)
    
    def all_with_deleted(self):
        """Return all objects including soft-deleted ones."""
        return super().get_queryset()
    
    def deleted_only(self):
        """Return only soft-deleted objects."""
        return super().get_queryset().filter(is_deleted=True)


class OrderedModel(models.Model):
    """
    Abstract model that provides ordering functionality.
    Useful for blocks, cards, and other ordered items.
    """
    position = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        abstract = True
        ordering = ['position']

    def move_to(self, new_position):
        """
        Move this item to a new position, adjusting siblings accordingly.
        """
        raise NotImplementedError("Subclasses must implement move_to()")
