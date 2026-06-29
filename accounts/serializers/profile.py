from rest_framework import serializers
from accounts.models import Profile
from content.models import Category
from content.serializers import CategoryStudentSerializer

class ProfileSerializer(serializers.ModelSerializer):
    current_category = CategoryStudentSerializer(read_only=True)
    current_category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        source='current_category',
        write_only=True,
        required=False,
        allow_null=True
    )

    class Meta:
        model = Profile
        fields = [
            'id', 'first_name', 'last_name', 'avatar', 'phone', 'address',
            'birth_date', 'gender',
            'current_category', 'current_category_id'
        ]