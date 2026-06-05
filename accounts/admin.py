from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Profile

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'email', 'first_name', 'last_name', 'is_staff']
    list_filter = ['is_superuser', 'is_staff']

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "username", "usable_password", "password1", "password2"),
            },
        ),
    )

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'gender', 'phone', 'address', 'birth_date']
    list_filter = ['gender']
    list_select_related = ['user']