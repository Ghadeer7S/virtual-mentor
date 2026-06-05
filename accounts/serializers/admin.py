from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework.exceptions import PermissionDenied
from djoser.serializers import UserCreateSerializer as BaseUserCreateSerializer
from djoser.serializers import UserSerializer as BaseUserSerializer
from accounts.models import Profile, User
from rest_framework import serializers


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


class DashboardUserCreateSerializer(BaseUserCreateSerializer):
    """Admin creates users — role and is_active are writable"""

    class Meta(BaseUserCreateSerializer.Meta):
        fields = ['id', 'username', 'email', 'password',
                  'first_name', 'last_name', 'role', 'is_active']
        read_only_fields = ['is_active']

    def create(self, validated_data):
        # Admin-created accounts are active immediately
        validated_data['is_active'] = True
        return super().create(validated_data)


class DashboardUserSerializer(BaseUserSerializer):

    class Meta(BaseUserSerializer.Meta):
        fields = ['id', 'username', 'email', 'first_name',
                  'last_name', 'role', 'is_active']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')

        if request and request.user.role != 'admin':
            self.fields['role'].read_only = True
            self.fields['is_active'].read_only = True

    def update(self, instance, validated_data):
        request = self.context.get('request')

        if request and request.user.role != 'admin':
            validated_data.pop('role', None)
            validated_data.pop('is_active', None)

        # prevent last admin from changing his own role
        if request and instance == request.user and request.user.role == 'admin':
            admin_count = User.objects.filter(role='admin').count()
            if admin_count <= 1:
                validated_data.pop('role', None)

        return super().update(instance, validated_data)
    

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