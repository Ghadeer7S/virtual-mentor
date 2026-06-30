import random
from accounts.models import OTPVerification, PasswordResetOTP
from accounts.emails import send_activation_email, send_reset_email


def send_otp(user):
    code = str(random.randint(100000, 999999))
    OTPVerification.objects.update_or_create(
        user=user,
        defaults={'code': code}
    )
    user.refresh_from_db()
    first_name = user.profile.first_name or user.email
    send_activation_email.delay(user.email, first_name, code)


def send_reset_otp(user):
    code = str(random.randint(100000, 999999))
    PasswordResetOTP.objects.update_or_create(
        user=user,
        defaults={'code': code}
    )
    user.refresh_from_db()
    first_name = user.profile.first_name or user.email
    send_reset_email.delay(user.email, first_name, code)