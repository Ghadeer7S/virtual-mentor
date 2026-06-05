from rest_framework.permissions import BasePermission

class NobodyPermission(BasePermission):
    """Disables the endpoint completely"""
    def has_permission(self, request, view):
        return False

class IsAdminOnly(BasePermission):
    """All existing endpoints — admin only"""
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.role == 'admin'
        )


class IsEditorOnly(BasePermission):
    """Reserved for future editor endpoints"""
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.role == 'editor'
        )
