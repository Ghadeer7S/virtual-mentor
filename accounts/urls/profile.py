from rest_framework.routers import DefaultRouter

from accounts.views.profile import ProfileViewSet

router = DefaultRouter()
router.register('profiles', ProfileViewSet, basename='profiles')

urlpatterns = router.urls