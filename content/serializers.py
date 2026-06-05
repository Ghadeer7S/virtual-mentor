from rest_framework import serializers
from .models import (
                        Category, Subject, Skill,PlacementQuestion,
                        Concept, Question
                    )


# ─── Placement Questions ──────────────────────────────────────────────────────

class PlacementQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlacementQuestion
        fields = [
            'id', 'question', 'question_type', 'level',
            'concept', 'options', 'correct_answer'
        ]


class PlacementQuestionStudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlacementQuestion
        fields = [
            'id', 'question', 'question_type',
            'level', 'concept', 'options'
        ]


# ─── Questions ────────────────────────────────────────────────────────────────

class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = [
            'id', 'question_type', 'question',
            'options', 'correct_answer', 'explanation',
            'hint'
        ]


class QuestionStudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = [
            'id', 'question_type', 'question',
            'options', 'hint'
        ]


# ─── Concepts ─────────────────────────────────────────────────────────────────

class ConceptSerializer(serializers.ModelSerializer):
    # questions = QuestionSerializer(many=True, read_only=True)

    class Meta:
        model = Concept
        fields = [
            'id', 'name', 'explanation',
            'examples'
        ]


class ConceptStudentSerializer(serializers.ModelSerializer):
    # questions = QuestionStudentSerializer(many=True, read_only=True)

    class Meta:
        model = Concept
        fields = [
            'id', 'name', 'explanation',
            'examples'
        ]


# ─── Skill ────────────────────────────────────────────────────────────────────

class SkillSerializer(serializers.ModelSerializer):
    # placement_questions = PlacementQuestionSerializer(many=True, read_only=True)
    # lessons = LessonSerializer(many=True, read_only=True)
    created_by_email = serializers.CharField(
        source='created_by.email', read_only=True
    )

    class Meta:
        model = Skill
        fields = [
            'id', 'subject', 'name', 'description',
            'is_active', 'created_at',
            'created_by_email'
        ]
        read_only_fields = ['subject', 'created_at', 'created_by_email']

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


class SkillStudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = [
            'id', 'name', 'description'
        ]


# ─── Subject ──────────────────────────────────────────────────────────────────

class SubjectSerializer(serializers.ModelSerializer):
    # skills = SkillSerializer(many=True, read_only=True)

    class Meta:
        model = Subject
        fields = [
            'id', 'category', 'name', 'description',
            'icon', 'is_active', 'created_at'
        ]
        read_only_fields = ['category', 'created_at']


class SubjectStudentSerializer(serializers.ModelSerializer):
    # skills = SkillStudentSerializer(many=True, read_only=True)

    class Meta:
        model = Subject
        fields = ['id', 'name', 'description', 'icon']


# ─── Category ─────────────────────────────────────────────────────────────────

class CategorySerializer(serializers.ModelSerializer):
    # subjects = SubjectSerializer(many=True, read_only=True)

    class Meta:
        model = Category
        fields = [
            'id', 'name', 'description', 'icon',
            'is_active', 'created_at'
        ]
        read_only_fields = ['created_at']


class CategoryStudentSerializer(serializers.ModelSerializer):
    # subjects = SubjectStudentSerializer(many=True, read_only=True)

    class Meta:
        model = Category
        fields = ['id', 'name', 'description', 'icon']