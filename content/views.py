from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import Category, Subject, Skill, PlacementQuestion, Concept, TrainingQuestion
from .permissions import IsAdminOrEditor, IsAdminOrEditorOrReadOnly
from .serializers import (
    CategorySerializer, CategoryStudentSerializer, ConceptPlacementQuestionSerializer,
    SubjectSerializer, SubjectStudentSerializer,
    SkillSerializer, SkillStudentSerializer,
    PlacementQuestionSerializer, PlacementQuestionStudentSerializer,
    ConceptSerializer, ConceptStudentSerializer,
    TrainingQuestionSerializer, TrainingQuestionStudentSerializer,
)
from accounts.pagination import DynamicPagination
# from rest_framework.filters import SearchFilter
from django_filters.rest_framework import DjangoFilterBackend
from .filters import RoleAwareSearchFilter

def is_editor_or_admin(user):
    return (
        user.is_authenticated
        and user.role in ('admin', 'editor')
    )


# ─── Category ─────────────────────────────────────────────────────────────────

class CategoryViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrEditorOrReadOnly]
    pagination_class = DynamicPagination
    
    filter_backends = [DjangoFilterBackend, RoleAwareSearchFilter]
    filterset_fields = ['is_active']
    search_fields = [
        'name', 'description', 'icon', 'created_at'
    ]
    student_search_fields = ['name', 'description', 'icon']

    def get_queryset(self):
        if is_editor_or_admin(self.request.user):
            return Category.objects.all()
        return Category.objects.filter(is_active=True)

    def get_serializer_class(self):
        if is_editor_or_admin(self.request.user):
            return CategorySerializer
        return CategoryStudentSerializer
    
    def paginate_queryset(self, queryset):

        paginate = self.request.query_params.get('paginate')

        if paginate == 'true':
            return super().paginate_queryset(queryset)

        return None


# ─── Subject ──────────────────────────────────────────────────────────────────

class SubjectViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrEditorOrReadOnly]
    pagination_class = DynamicPagination
    filter_backends = [DjangoFilterBackend, RoleAwareSearchFilter]
    
    filterset_fields = ['is_active']
    search_fields = [
        'name', 'description', 'icon', 'created_at'
    ]
    student_search_fields = ['name', 'description', 'icon']

    def get_queryset(self):
        category_id = self.kwargs.get('category_pk')
        qs = Subject.objects.select_related('category')
        if category_id:
            qs = qs.filter(category_id=category_id)
        if not is_editor_or_admin(self.request.user):
            qs = qs.filter(is_active=True)
        return qs

    def get_serializer_class(self):
        if is_editor_or_admin(self.request.user):
            return SubjectSerializer
        return SubjectStudentSerializer

    def perform_create(self, serializer):
        category_id = self.kwargs.get('category_pk')
        serializer.save(category_id=category_id)

    def paginate_queryset(self, queryset):

        paginate = self.request.query_params.get('paginate')

        if paginate == 'true':
            return super().paginate_queryset(queryset)

        return None

# ─── Skill ────────────────────────────────────────────────────────────────────

class SkillViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrEditorOrReadOnly]
    pagination_class = DynamicPagination
    filter_backends = [DjangoFilterBackend, RoleAwareSearchFilter]
    
    filterset_fields = ['is_active']
    search_fields = [
        'name', 'description', 'created_at'
    ]
    student_search_fields = ['name', 'description']

    def get_queryset(self):
        category_id = self.kwargs.get('category_pk')
        subject_id = self.kwargs.get('subject_pk')

        qs = Skill.objects.select_related(
            'subject',
            'subject__category'
        ).filter(
            subject_id=subject_id,
            subject__category_id=category_id
        )

        if not is_editor_or_admin(self.request.user):
            qs = qs.filter(is_active=True)

        return qs

    def get_serializer_class(self):
        if is_editor_or_admin(self.request.user):
            return SkillSerializer
        return SkillStudentSerializer

    def perform_create(self, serializer):
        subject_id = self.kwargs.get('subject_pk')
        serializer.save(subject_id=subject_id)

    def paginate_queryset(self, queryset):

        paginate = self.request.query_params.get('paginate')

        if paginate == 'true':
            return super().paginate_queryset(queryset)

        return None


# ─── PlacementQuestion ────────────────────────────────────────────────────────

class PlacementQuestionViewSet(viewsets.ModelViewSet):

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAuthenticated()]
        return [IsAdminOrEditor()]

    def get_serializer_class(self):
        concept_id = self.kwargs.get('concept_pk')
        
        if concept_id:
            return ConceptPlacementQuestionSerializer
        
        if is_editor_or_admin(self.request.user):
            return PlacementQuestionSerializer
        return PlacementQuestionStudentSerializer

    def get_queryset(self):
        category_id = self.kwargs.get('category_pk')
        subject_id = self.kwargs.get('subject_pk')
        skill_id = self.kwargs.get('skill_pk')
        concept_id = self.kwargs.get('concept_pk')

        qs = PlacementQuestion.objects.select_related(
            'skill',
            'skill__subject',
            'skill__subject__category',
            'concept'
        ).filter(
            skill_id=skill_id,
            skill__subject_id=subject_id,
            skill__subject__category_id=category_id
        )

        if concept_id:
            qs = qs.filter(concept_id=concept_id)

        return qs
    
    def create(self, request, *args, **kwargs):

        many = isinstance(request.data, list)

        serializer = self.get_serializer(
            data=request.data,
            many=many
        )

        serializer.is_valid(raise_exception=True)

        skill_id = self.kwargs.get('skill_pk')

        concept_id = self.kwargs.get('concept_pk')

        if concept_id:
            serializer.save(
                skill_id=skill_id,
                concept_id=concept_id
            )
        else:
            serializer.save(skill_id=skill_id)

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED
        )



# ─── Concept ──────────────────────────────────────────────────────────────────

class ConceptViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrEditorOrReadOnly]

    def get_queryset(self):
        category_id = self.kwargs.get('category_pk')
        subject_id = self.kwargs.get('subject_pk')
        skill_id = self.kwargs.get('skill_pk')

        return Concept.objects.select_related(
            'skill',
            'skill__subject',
            'skill__subject__category'
        ).filter(
            skill_id=skill_id,
            skill__subject_id=subject_id,
            skill__subject__category_id=category_id
        )

    def get_serializer_class(self):
        if is_editor_or_admin(self.request.user):
            return ConceptSerializer
        return ConceptStudentSerializer

    def perform_create(self, serializer):
        skill_id = self.kwargs.get('skill_pk')
        serializer.save(skill_id=skill_id)


# ─── Question ─────────────────────────────────────────────────────────────────

class TrainingQuestionViewSet(viewsets.ModelViewSet):

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAuthenticated()]
        return [IsAdminOrEditor()]

    def get_queryset(self):
        category_id = self.kwargs.get('category_pk')
        subject_id = self.kwargs.get('subject_pk')
        skill_id = self.kwargs.get('skill_pk')
        concept_id = self.kwargs.get('concept_pk')

        qs = TrainingQuestion.objects.select_related(
            'concept',
            'concept__skill',
            'concept__skill__subject',
            'concept__skill__subject__category'
        ).filter(
            concept_id=concept_id,
            concept__skill_id=skill_id,
            concept__skill__subject_id=subject_id,
            concept__skill__subject__category_id=category_id
        )
        return qs

    def get_serializer_class(self):
        if is_editor_or_admin(self.request.user):
            return TrainingQuestionSerializer
        return TrainingQuestionStudentSerializer

    def create(self, request, *args, **kwargs):

        many = isinstance(request.data, list)

        serializer = self.get_serializer(
            data=request.data,
            many=many
        )

        serializer.is_valid(raise_exception=True)

        concept_id = self.kwargs.get('concept_pk')

        serializer.save(concept_id=concept_id)

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED
        )