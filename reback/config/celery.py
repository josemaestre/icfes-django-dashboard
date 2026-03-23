"""
Celery configuration for reback project.
"""
import os
from celery import Celery
from celery.schedules import crontab

# Set default Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')

app = Celery('reback')

# Load config from Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from all installed apps
app.autodiscover_tasks()

# Celery Beat schedule for recurring tasks
app.conf.beat_schedule = {}

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
