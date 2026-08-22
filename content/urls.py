from rest_framework_nested import routers
from django.urls import path, include
from .views import (
    CategoryViewSet,
    SubjectViewSet,
    SkillViewSet,
    PlacementQuestionViewSet,
    ConceptViewSet,
    TrainingQuestionViewSet,
    ChannelViewSet,
    ChannelMessageViewSet
)

# /api/categories/
router = routers.DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='category')

# /api/categories/{category_pk}/subjects/
categories_router = routers.NestedDefaultRouter(
    router,
    r'categories',
    lookup='category'
)
categories_router.register(
    r'subjects',
    SubjectViewSet,
    basename='category-subjects'
)

# /api/categories/{category_pk}/subjects/{subject_pk}/skills/
subjects_router = routers.NestedDefaultRouter(
    categories_router,
    r'subjects',
    lookup='subject'
)
subjects_router.register(
    r'skills',
    SkillViewSet,
    basename='subject-skills'
)

# /api/categories/{category_pk}/subjects/{subject_pk}/skills/{skill_pk}/placement-questions/
skills_router = routers.NestedDefaultRouter(
    subjects_router,
    r'skills',
    lookup='skill'
)

skills_router.register(
    r'placement-questions',
    PlacementQuestionViewSet,
    basename='skill-placement-questions'
)

# /api/categories/{category_pk}/subjects/{subject_pk}/skills/{skill_pk}/concepts/
skills_router.register(
    r'concepts',
    ConceptViewSet,
    basename='skill-concepts'
)

# /api/categories/{category_pk}/subjects/{subject_pk}/skills/{skill_pk}/channels/
skills_router.register(
    r'channels',
    ChannelViewSet,
    basename='skill-channels'
)


# /api/categories/{category_pk}/subjects/{subject_pk}/skills/{skill_pk}/channels/{channel_pk}/messages/
channels_router = routers.NestedDefaultRouter(
skills_router,
r'channels',
lookup='channel'
)

channels_router.register(
r'messages',
ChannelMessageViewSet,
basename='channel-messages'
)


# /api/categories/{category_pk}/subjects/{subject_pk}/skills/{skill_pk}/concepts/{concept_pk}/questions/
concepts_router = routers.NestedDefaultRouter(
    skills_router,
    r'concepts',
    lookup='concept'
)

concepts_router.register(
    r'questions',
    TrainingQuestionViewSet,
    basename='concept-questions'
)

concepts_router.register(
    r'placement-questions',
    PlacementQuestionViewSet,
    basename='concept-placement-questions'
)

urlpatterns = [
    path('', include(router.urls)),
    path('', include(categories_router.urls)),
    path('', include(subjects_router.urls)),
    path('', include(skills_router.urls)),
    path('', include(concepts_router.urls)),
    path('', include(channels_router.urls)),
]