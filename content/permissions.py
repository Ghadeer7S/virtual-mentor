from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAdminOrEditor(BasePermission):
    """Only admin and editor can write."""
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return request.user.role in ('admin', 'editor')


class IsAdminOrEditorOrReadOnly(BasePermission):
    """
    Students read only.
    admin and editor can write, update and delete.
    """
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return (
            request.user.is_authenticated
            and request.user.role in ('admin', 'editor')
        )
