from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
import random
from .models import Profile, OTPVerification, PasswordResetOTP
from .emails import send_activation_email, send_reset_email


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
        if not instance.is_active:
            _send_otp(instance)


def _send_otp(user):
    code = str(random.randint(100000, 999999))
    OTPVerification.objects.update_or_create(
        user=user,
        defaults={'code': code}
    )
    send_activation_email(user, code)


def _send_reset_otp(user):
    code = str(random.randint(100000, 999999))
    PasswordResetOTP.objects.update_or_create(
        user=user,
        defaults={'code': code}
    )
    send_reset_email(user, code)