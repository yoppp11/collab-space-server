"""
Notification Celery Tasks
"""
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings


@shared_task
def send_pending_notifications():
    """
    Send email notifications for unread notifications.
    Runs every minute via Celery Beat.
    """
    from .models import Notification
    from django.utils import timezone
    from datetime import timedelta
    
    # Get notifications from last 5 minutes that haven't been emailed
    cutoff = timezone.now() - timedelta(minutes=5)
    
    notifications = Notification.objects.filter(
        created_at__gte=cutoff,
        is_read=False,
        metadata__emailed=False
    ).select_related('recipient', 'actor')
    
    sent_count = 0
    
    for notification in notifications:
        if notification.recipient.preferences.get('notification_email', True):
            # Send email
            send_mail(
                subject=notification.title,
                message=notification.message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[notification.recipient.email],
                fail_silently=True,
            )
            
            # Mark as emailed
            notification.metadata['emailed'] = True
            notification.save()
            sent_count += 1
    
    return f"Sent {sent_count} email notifications"


@shared_task
def cleanup_old_notifications(days: int = 90):
    """
    Delete old read notifications.
    """
    from .models import Notification
    from django.utils import timezone
    from datetime import timedelta
    
    cutoff = timezone.now() - timedelta(days=days)
    
    deleted_count = Notification.objects.filter(
        is_read=True,
        read_at__lt=cutoff
    ).delete()[0]
    
    return f"Deleted {deleted_count} old notifications"
