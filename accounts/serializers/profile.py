from rest_framework import serializers
from accounts.models import Profile

class ProfileSerializer(serializers.ModelSerializer):

    class Meta:
        model = Profile
        fields = ['id', 'avatar', 'phone', 'address', 'birth_date', 'gender']