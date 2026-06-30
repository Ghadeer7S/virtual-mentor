from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings


@shared_task
def send_activation_email(user_email, user_first_name, code):
    html_message = f"""
    <div style="font-family: Arial, sans-serif; max-width: 500px; margin: auto; padding: 30px; border: 1px solid #e0e0e0; border-radius: 10px;">
        <h2 style="color: #4A90E2;">Welcome to Our App 👋</h2>
        <p style="font-size: 16px; color: #333;">
            Thank you for registering, <strong>{user_first_name}</strong>!<br>
            We hope you enjoy a great learning journey with us.
        </p>
        <p style="font-size: 16px; color: #333;">Your activation code is:</p>
        <div style="text-align: center; margin: 20px 0;">
            <span style="font-size: 36px; font-weight: bold; letter-spacing: 8px; color: #4A90E2; border-bottom: 3px solid #4A90E2; padding-bottom: 5px;">
                {code}
            </span>
        </div>
        <p style="font-size: 13px; color: #999;">
            This code is valid for <strong>10 minutes</strong>. Do not share it with anyone.
        </p>
        <hr style="border: none; border-top: 1px solid #e0e0e0; margin: 20px 0;">
        <p style="font-size: 12px; color: #bbb; text-align: center;">
            If you did not create an account, please ignore this email.
        </p>
    </div>
    """
    send_mail(
        subject='Your Activation Code',
        message=f'Your activation code is: {code}\nValid for 10 minutes.',
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user_email],
        html_message=html_message,
        fail_silently=False,
    )


@shared_task
def send_reset_email(user_email, user_first_name, code):
    html_message = f"""
    <div style="font-family: Arial, sans-serif; max-width: 500px; margin: auto; padding: 30px; border: 1px solid #e0e0e0; border-radius: 10px;">
        <h2 style="color: #4A90E2;">Password Reset Request 🔐</h2>
        <p style="font-size: 16px; color: #333;">
            Hello, <strong>{user_first_name}</strong>!<br>
            We received a request to reset your password.
        </p>
        <p style="font-size: 16px; color: #333;">Your password reset code is:</p>
        <div style="text-align: center; margin: 20px 0;">
            <span style="font-size: 36px; font-weight: bold; letter-spacing: 8px; color: #4A90E2; border-bottom: 3px solid #4A90E2; padding-bottom: 5px;">
                {code}
            </span>
        </div>
        <p style="font-size: 13px; color: #999;">
            This code is valid for <strong>10 minutes</strong>. Do not share it with anyone.
        </p>
        <hr style="border: none; border-top: 1px solid #e0e0e0; margin: 20px 0;">
        <p style="font-size: 12px; color: #bbb; text-align: center;">
            If you did not request a password reset, please ignore this email.
        </p>
    </div>
    """
    send_mail(
        subject='Password Reset Code',
        message=f'Your password reset code is: {code}\nValid for 10 minutes.',
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user_email],
        html_message=html_message,
        fail_silently=False,
    )