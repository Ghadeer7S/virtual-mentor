from rest_framework import serializers
from .models import PlacementSession, PlacementSessionQuestion, PlacementAnswer
from content.serializers import PlacementQuestionStudentSerializer, SkillStudentSerializer, ConceptStudentSerializer


# ───── عرض الجلسة للطالب ─────

class PlacementSessionQuestionSerializer(serializers.ModelSerializer):
    question = PlacementQuestionStudentSerializer(read_only=True)

    class Meta:
        model = PlacementSessionQuestion
        fields = ['order', 'question']


class PlacementSessionSerializer(serializers.ModelSerializer):
    questions = PlacementSessionQuestionSerializer(
        source='session_questions',
        many=True,
        read_only=True
    )

    class Meta:
        model = PlacementSession
        fields = ['id', 'skill', 'started_at', 'questions']

class PlacementSessionHistorySerializer(serializers.ModelSerializer):
    skill_name = serializers.CharField(source='skill.name', read_only=True)

    class Meta:
        model = PlacementSession
        fields = [
            'id', 'skill', 'skill_name',
            'started_at', 'completed_at', 'result'
        ]

# ───── إرسال الإجابات ─────

class PlacementAnswerInputSerializer(serializers.Serializer):
    question_id = serializers.IntegerField()
    user_answer = serializers.CharField(allow_blank=True)


class PlacementSubmitSerializer(serializers.Serializer):
    answers = PlacementAnswerInputSerializer(many=True)

    def validate_answers(self, value):
        if not value:
            raise serializers.ValidationError('At least one answer must be submitted')
        return value
    
#------------------------------------------------

from .models import UserSkillProfile, UserConceptProfile


class UserSkillProfileSerializer(serializers.ModelSerializer):
    skill = SkillStudentSerializer(read_only=True)
    is_started = serializers.SerializerMethodField()

    class Meta:
        model = UserSkillProfile
        fields = [
            'id', 'skill', 'is_started', 'current_level',
            'assessment_score', 'is_mastered', 'mastered_at',
            'total_assessments', 'last_assessed_at',
            'can_reassess_at', 'xp_total'
        ]
    
    def get_is_started(self, obj):
        return True

class SkillNotStartedSerializer(serializers.Serializer):
    id         = serializers.IntegerField()
    skill      = SkillStudentSerializer(source='*', read_only=True)
    is_started = serializers.SerializerMethodField()

    def get_is_started(self, obj):
        return False


class UserConceptProfileSerializer(serializers.ModelSerializer):
    concept = ConceptStudentSerializer(read_only=True)

    class Meta:
        model = UserConceptProfile
        fields = [
            'id', 'concept', 'status',
            'avg_score', 'times_trained', 'updated_at'
        ]