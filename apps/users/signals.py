"""
User Signals
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

User = get_user_model()


@receiver(post_save, sender=User)
def user_post_save(sender, instance, created, **kwargs):
    """
    Signal handler for post-save user events.
    """
    if created:
        # Initialize user preferences with defaults
        if not instance.preferences:
            instance.preferences = {
                'theme': 'system',
                'notification_email': True,
                'notification_push': True,
                'notification_mentions': True,
                'sidebar_collapsed': False,
                'default_view': 'list'
            }
            instance.save(update_fields=['preferences'])
