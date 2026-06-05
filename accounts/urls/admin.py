from django.urls import path
from rest_framework.routers import DefaultRouter

from accounts.views.admin import (
    DashboardLoginView,
    DashboardUserViewSet,
    DashboardProfileViewSet,
)

router = DefaultRouter()

router.register(
    'users',
    DashboardUserViewSet,
    basename='dashboard-users'
)

router.register(
    'profiles',
    DashboardProfileViewSet,
    basename='dashboard-profiles'
)

urlpatterns = router.urls + [
    path(
        'auth/login/',
        DashboardLoginView.as_view(),
        name='dashboard-login'
    ),
]