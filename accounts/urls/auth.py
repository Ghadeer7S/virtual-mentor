from django.urls import path

from accounts.views.auth import (
    VerifyOTPView,
    ResendOTPView,
    ForgotPasswordView,
    ResetPasswordView,
    GoogleLoginView,
)

urlpatterns = [
    path('verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    path('resend-otp/', ResendOTPView.as_view(), name='resend-otp'),
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset-password'),
    path('auth/google/', GoogleLoginView.as_view(), name='google-login'),
]