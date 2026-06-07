from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from djoser.serializers import UserCreateSerializer as BaseUserCreateSerializer
from djoser.serializers import UserSerializer as BaseUserSerializer
from accounts.models import Profile, User
from accounts.serializers.profile import ProfileSerializer


class DashboardTokenSerializer(TokenObtainPairSerializer):

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['role'] = user.role
        return token

    def validate(self, attrs):
            data = super().validate(attrs)

            if self.user.role not in ['admin', 'editor']:
                raise PermissionDenied(
                    "You do not have permission to access this resource."
                )
            
            data['role'] = self.user.role

            return data


class DashboardUserCreateSerializer(serializers.ModelSerializer):

    profile = ProfileSerializer(required=False)

    password = serializers.CharField(write_only=True)

    class Meta:
        model = User

        fields = [
            'id',
            'email',
            'password',
            'first_name',
            'last_name',
            'role',
            'is_active',
            'profile'
        ]

        read_only_fields = ['is_active']

    def create(self, validated_data):

        profile_data = validated_data.pop('profile', {})

        password = validated_data.pop('password')

        validated_data['is_active'] = True

        user = User.objects.create(**validated_data)

        user.set_password(password)

        user.save()

        Profile.objects.update_or_create(
            user=user,
            defaults=profile_data
        )

        user.refresh_from_db()

        return user


class DashboardUserSerializer(BaseUserSerializer):
    profile = ProfileSerializer(read_only=True)

    class Meta(BaseUserSerializer.Meta):
        fields = ['id', 'email', 'first_name',
                  'last_name', 'role', 'is_active', 'profile']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')

        if request and request.user.role != 'admin':
            self.fields['role'].read_only = True
            self.fields['is_active'].read_only = True

    def update(self, instance, validated_data):
        profile_data = self.initial_data.get('profile')

        request = self.context.get('request')

        if request and request.user.role != 'admin':
            validated_data.pop('role', None)
            validated_data.pop('is_active', None)

        # prevent last admin from changing his own role
        if request and instance == request.user and request.user.role == 'admin':
            admin_count = User.objects.filter(role='admin').count()
            if admin_count <= 1:
                validated_data.pop('role', None)

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

class DeleteAccountSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)

    def validate_current_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Invalid password.')
        return value


class DashboardProfileSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = Profile
        fields = ['id', 'user_email', 'avatar', 'phone',
                  'address', 'birth_date', 'gender']