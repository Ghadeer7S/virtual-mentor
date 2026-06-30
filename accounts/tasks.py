from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from accounts.models import User


@shared_task
def delete_unactivated_users():
    from django.utils import timezone
    from datetime import timedelta
    from accounts.models import User
    
    expiry_time = timezone.now() - timedelta(hours=24)
    User.objects.filter(
        is_active=False,
        date_joined__lt=expiry_time,
        role='student'
    ).delete()