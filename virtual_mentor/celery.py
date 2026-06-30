import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'virtual_mentor.settings')

app = Celery('virtual_mentor')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'delete-unactivated-users-every-hour': {
        'task': 'accounts.tasks.delete_unactivated_users',
        'schedule': crontab(minute=0, hour='*/1'),
    },
}