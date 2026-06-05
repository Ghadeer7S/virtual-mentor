from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAdminOrEditor(BasePermission):
    """admin و editor فقط يقدرون يكتبون"""
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return request.user.role in ('admin', 'editor')


class IsAdminOrEditorOrReadOnly(BasePermission):
    """
    الطالب يقرأ فقط.
    admin و editor يقدرون يكتبون ويعدلون ويحذفون.
    """
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return request.user.is_authenticated
        return (
            request.user.is_authenticated
            and request.user.role in ('admin', 'editor')
        )
