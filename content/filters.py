from rest_framework.filters import SearchFilter


def is_editor_or_admin(user):
    return (
        user.is_authenticated
        and user.role in ('admin', 'editor')
    )

class RoleAwareSearchFilter(SearchFilter):
    def get_search_fields(self, view, request):
        if is_editor_or_admin(request.user):
            return getattr(view, 'search_fields', [])
        return getattr(view, 'student_search_fields', [])