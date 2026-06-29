import random
from accounts.models import OTPVerification, PasswordResetOTP
from accounts.emails import send_activation_email, send_reset_email


def send_otp(user):
    code = str(random.randint(100000, 999999))
    OTPVerification.objects.update_or_create(
        user=user,
        defaults={'code': code}
    )
    send_activation_email(user, code)


def send_reset_otp(user):
    code = str(random.randint(100000, 999999))
    PasswordResetOTP.objects.update_or_create(
        user=user,
        defaults={'code': code}
    )
    send_reset_email(user, code)