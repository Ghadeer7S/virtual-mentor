from djoser.serializers import (
                                UserCreateSerializer as BaseUserCreateSerializer,
                                UserSerializer as BaseUserSerializer)
from django.core.exceptions import ValidationError as DjangoValidationError
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from accounts.serializers.profile import ProfileSerializer
from accounts.models import User, Profile
from accounts.services.user_service import send_otp
from django.db import transaction


class UserCreateSerializer(serializers.ModelSerializer):

    profile = ProfileSerializer(required=False)

    password = serializers.CharField(
        write_only=True,
        validators=[validate_password]
    )

    class Meta:
        model = User
        fields = ['id', 'email', 'password', 'profile']
        extra_kwargs = {
            'email': {'validators': []}
        }

    def validate_email(self, value):
        value = value.lower().strip()

        if User.objects.filter(email=value, is_active=True).exists():
            raise serializers.ValidationError("A user with this email already exists.")

        if User.objects.filter(email=value, is_active=False).exclude(
            role=User.ROLE_STUDENT
        ).exists():
            raise serializers.ValidationError("A user with this email already exists.")

        return value

    @transaction.atomic
    def create(self, validated_data):
        profile_data = validated_data.pop('profile', {})
        password = validated_data.pop('password')
        email = validated_data['email']

        existing_user = User.objects.select_for_update().filter(
            email=email,
            is_active=False,
            role=User.ROLE_STUDENT
        ).first()

        if existing_user:
            for field, value in validated_data.items():
                setattr(existing_user, field, value)
            existing_user.set_password(password)
            existing_user.role = User.ROLE_STUDENT
            existing_user.save()
            user = existing_user
        else:
            validated_data['role'] = User.ROLE_STUDENT
            user = User.objects.create_user(password=password, **validated_data)

        Profile.objects.update_or_create(
            user=user,
            defaults=profile_data
        )

        user.refresh_from_db()

        if not user.is_active:
            transaction.on_commit(lambda: send_otp(user))

        return user

class UserSerializer(BaseUserSerializer):
    profile = ProfileSerializer(read_only=True)
    
    class Meta(BaseUserSerializer.Meta):
        fields = ['id', 'email', 'profile']

    def update(self, instance, validated_data):

        profile_data = self.initial_data.get('profile')

        user = super().update(instance, validated_data)

        if profile_data:
            profile_serializer = ProfileSerializer(
                instance.profile,
                data=profile_data,
                partial=True
            )

            profile_serializer.is_valid(raise_exception=True)

            profile_serializer.save()

        return user

# -----------------------------Activation----------------------------------

class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6)

class ResendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()

# ---------------------------Reset-Password------------------------------------

class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    
class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6)
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate_new_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.messages)
        return value

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({'confirm_password': 'Passwords do not match'})
        return attrs