from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings
import random
from django.utils import timezone
from datetime import timedelta

class User(AbstractUser):
    ROLE_STUDENT = 'student'
    ROLE_EDITOR = 'editor'
    ROLE_ADMIN = 'admin'

    ROLE_CHOICES = [
        (ROLE_STUDENT, 'Student'),
        (ROLE_EDITOR, 'Editor'),
        (ROLE_ADMIN, 'Admin'),
    ]

    username = models.CharField(max_length=200, unique=False)
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=False)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_STUDENT)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ['username']

    def save(self, *args, **kwargs):

        if self.is_superuser:
            self.role = self.ROLE_ADMIN
            self.is_staff = True

        elif self.role == self.ROLE_ADMIN:
            self.is_staff = True

        else:
            self.is_staff = False

        super().save(*args, **kwargs)

class Profile(models.Model):
    GENDER_MALE = 'M'
    GENDER_FEMALE = 'F'

    GENDER_CHOICES = [
        (GENDER_MALE, 'Male'),
        (GENDER_FEMALE, 'Female')
    ]
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    phone = models.CharField(max_length=255, blank=True)
    address = models.CharField(max_length=255, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True)


class OTPVerification(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='otp_verification')
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now=True)
    attempts = models.PositiveSmallIntegerField(default=0)

    def is_expired(self):
        # الكود صالح لمدة 10 دقائق
        return timezone.now() > self.created_at + timedelta(minutes=10)
    
    def is_on_cooldown(self):
        return timezone.now() < self.created_at + timedelta(minutes=2)

    def __str__(self):
        return f"{self.user.email} - {self.code}"
    
class PasswordResetOTP(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='password_reset_otp')
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now=True)
    attempts = models.PositiveSmallIntegerField(default=0)

    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(minutes=10)

    def is_on_cooldown(self):
        return timezone.now() < self.created_at + timedelta(minutes=2)

    def __str__(self):
        return f"{self.user.email} - {self.code}"