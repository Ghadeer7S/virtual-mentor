from celery import shared_task
from django.utils import timezone

from .constants import STALE_SESSION_AGE
from .models import PlacementSession, TrainingSession


@shared_task
def cleanup_stale_training_sessions():
    cutoff = timezone.now() - STALE_SESSION_AGE

    stale_sessions = TrainingSession.objects.filter(
        completed_at__isnull=True,
        started_at__lt=cutoff,
    )

    count = stale_sessions.count()
    stale_sessions.delete()

    return f'Deleted {count} pending training sessions'


@shared_task
def cleanup_stale_placement_sessions():
    cutoff = timezone.now() - STALE_SESSION_AGE

    stale_sessions = PlacementSession.objects.filter(
        completed_at__isnull=True,
        started_at__lt=cutoff,
    )

    count = stale_sessions.count()
    stale_sessions.delete()

    return f'Deleted {count} pending placement sessions'