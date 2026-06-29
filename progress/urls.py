from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    CategoryProgressView,
    ResetSkillProgressView,
    StartPlacementSessionView,
    SubmitPlacementSessionView,
    PlacementSessionHistoryViewSet,
    UserConceptProfileViewSet,
    UserSkillProfileViewSet,
    ProgressOverview
)

router = DefaultRouter()
router.register('placement-history', PlacementSessionHistoryViewSet, basename='placement-history')
router.register('skill-profiles', UserSkillProfileViewSet, basename='skill-profiles')
router.register('concept-profiles', UserConceptProfileViewSet, basename='concept-profiles')

urlpatterns = router.urls + [
    path(
        'categories/<int:category_pk>/subjects/<int:subject_pk>/skills/<int:skill_pk>/start-placement/',
        StartPlacementSessionView.as_view(),
        name='placement-start'
    ),
    path(
        'placement/<int:session_id>/submit/',
        SubmitPlacementSessionView.as_view(),
        name='placement-submit'
    ),
    path(
        'categories/<int:category_pk>/subjects/<int:subject_pk>/skills/<int:skill_pk>/reset-placement/',
        ResetSkillProgressView.as_view(),
        name='placement-reset'
    ),
    path('progress-overview/', ProgressOverview.as_view(), name='progress-overview'),
    
    path(
        'category-progress/<int:category_pk>/',
        CategoryProgressView.as_view(),
        name='category-progress'
    ),

    path(
        'categories/<int:category_pk>/subjects/<int:subject_pk>/skill-profiles/',
        UserSkillProfileViewSet.as_view({'get': 'list'}),
        name='skill-profiles-by-subject'
    ),
    path(
        'categories/<int:category_pk>/subjects/<int:subject_pk>/skills/<int:skill_pk>/concept-profiles/',
        UserConceptProfileViewSet.as_view({'get': 'list'}),
        name='concept-profiles-by-skill'
    ),

]