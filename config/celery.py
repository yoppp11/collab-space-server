"""
Celery Configuration for Real-time Collaboration Platform
"""
import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('collab_platform')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Celery Beat Schedule
app.conf.beat_schedule = {
    'cleanup-expired-sessions': {
        'task': 'apps.collaboration.tasks.cleanup_expired_sessions',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
    'cleanup-old-document-versions': {
        'task': 'apps.documents.tasks.cleanup_old_versions',
        'schedule': crontab(hour=3, minute=0),  # Daily at 3 AM
    },
    'send-pending-notifications': {
        'task': 'apps.notifications.tasks.send_pending_notifications',
        'schedule': crontab(minute='*/1'),  # Every minute
    },
    'generate-activity-reports': {
        'task': 'apps.workspaces.tasks.generate_activity_reports',
        'schedule': crontab(hour=0, minute=0, day_of_week='monday'),  # Weekly
    },
}

app.conf.task_routes = {
    'apps.notifications.tasks.*': {'queue': 'notifications'},
    'apps.documents.tasks.*': {'queue': 'documents'},
    'apps.collaboration.tasks.*': {'queue': 'collaboration'},
}


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
