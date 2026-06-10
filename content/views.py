from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Category, Subject, Skill, PlacementQuestion, Concept, Question
from .permissions import IsAdminOrEditor, IsAdminOrEditorOrReadOnly
from .serializers import (
    CategorySerializer, CategoryStudentSerializer,
    SubjectSerializer, SubjectStudentSerializer,
    SkillSerializer, SkillStudentSerializer,
    PlacementQuestionSerializer, PlacementQuestionStudentSerializer,
    ConceptSerializer, ConceptStudentSerializer,
    QuestionSerializer, QuestionStudentSerializer,
)


def is_editor_or_admin(user):
    return (
        user.is_authenticated
        and user.role in ('admin', 'editor')
    )


# ─── Category ─────────────────────────────────────────────────────────────────

class CategoryViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrEditorOrReadOnly]

    def get_queryset(self):
        if is_editor_or_admin(self.request.user):
            return Category.objects.all()
        return Category.objects.filter(is_active=True)

    def get_serializer_class(self):
        if is_editor_or_admin(self.request.user):
            return CategorySerializer
        return CategoryStudentSerializer


# ─── Subject ──────────────────────────────────────────────────────────────────

class SubjectViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrEditorOrReadOnly]

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


# ─── Skill ────────────────────────────────────────────────────────────────────

class SkillViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrEditorOrReadOnly]

    def get_queryset(self):
        subject_id = self.kwargs.get('subject_pk')
        qs = Skill.objects.select_related('subject__category')
        if subject_id:
            qs = qs.filter(subject_id=subject_id)
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


# ─── PlacementQuestion ────────────────────────────────────────────────────────

class PlacementQuestionViewSet(viewsets.ModelViewSet):

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAuthenticated()]
        return [IsAdminOrEditor()]

    def get_serializer_class(self):
        if is_editor_or_admin(self.request.user):
            return PlacementQuestionSerializer
        return PlacementQuestionStudentSerializer

    def get_queryset(self):
        skill_id = self.kwargs.get('skill_pk')
        return PlacementQuestion.objects.filter(skill_id=skill_id)

    def perform_create(self, serializer):
        skill_id = self.kwargs.get('skill_pk')
        serializer.save(skill_id=skill_id)




# ─── Concept ──────────────────────────────────────────────────────────────────

class ConceptViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrEditorOrReadOnly]

    def get_queryset(self):
        skill_id = self.kwargs.get('skill_pk')
        qs = Concept.objects.select_related('skill')
        if skill_id:
            qs = qs.filter(skill_id=skill_id)
        return qs

    def get_serializer_class(self):
        if is_editor_or_admin(self.request.user):
            return ConceptSerializer
        return ConceptStudentSerializer

    def perform_create(self, serializer):
        skill_id = self.kwargs.get('skill_pk')
        serializer.save(skill_id=skill_id)


# ─── Question ─────────────────────────────────────────────────────────────────

class QuestionViewSet(viewsets.ModelViewSet):

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAuthenticated()]
        return [IsAdminOrEditor()]

    def get_queryset(self):
        concept_id = self.kwargs.get('concept_pk')
        return Question.objects.filter(concept_id=concept_id)

    def get_serializer_class(self):
        if is_editor_or_admin(self.request.user):
            return QuestionSerializer
        return QuestionStudentSerializer

    def perform_create(self, serializer):
        concept_id = self.kwargs.get('concept_pk')
        serializer.save(concept_id=concept_id)