from rest_framework import serializers
from accounts.models import Profile

class ProfileSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = Profile
        fields = ['id', 'user_email', 'avatar', 'phone', 'address', 'birth_date', 'gender']