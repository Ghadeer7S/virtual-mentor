from celery import shared_task
from django.utils import timezone
from datetime import timedelta

from .models import TrainingSession


@shared_task
def cleanup_stale_training_sessions():
    cutoff = timezone.now() - timedelta(hours=24)

    stale_sessions = TrainingSession.objects.filter(
        completed_at__isnull=True,
        started_at__lt=cutoff,
    )

    count = stale_sessions.count()
    stale_sessions.delete()

    return f'تم حذف {count} جلسة تدريب معلّقة'