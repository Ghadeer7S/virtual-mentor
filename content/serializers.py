from rest_framework import serializers
from .models import (
                        Category, Subject, Skill,PlacementQuestion,
                        Concept, TrainingQuestion, Channel, ChannelMessage
                    )


# ─── Placement Questions ──────────────────────────────────────────────────────

class PlacementQuestionSerializer(serializers.ModelSerializer):
    concept_name = serializers.CharField(
        source='concept.name',
        read_only=True
    )

    class Meta:
        model = PlacementQuestion
        fields = [
            'id', 'image', 'question', 'question_type', 'level',
            'concept', 'concept_name', 'options', 'correct_answer'
        ]


class PlacementQuestionStudentSerializer(serializers.ModelSerializer):
    concept_name = serializers.CharField(
        source='concept.name',
        read_only=True
    )
    
    class Meta:
        model = PlacementQuestion
        fields = [
            'id', 'image', 'question', 'question_type',
            'level', 'concept_name', 'options'
        ]

class ConceptPlacementQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlacementQuestion
        fields = [
            'id', 'image', 'question', 'question_type', 'level', 'options',
            'correct_answer'
        ]

# ─── Training Questions ────────────────────────────────────────────────────────────────

class TrainingQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrainingQuestion
        fields = [
            'id', 'image', 'level', 'question_type', 'question',
            'options', 'correct_answer', 'explanation',
            'hint'
        ]


# ─── Concepts ─────────────────────────────────────────────────────────────────

class ConceptSerializer(serializers.ModelSerializer):
    # questions = QuestionSerializer(many=True, read_only=True)

    class Meta:
        model = Concept
        fields = [
            'id', 'name', 'explanation', 'reference_title',
            'reference_url', 'reference_type', 'is_active', 'order',
            'created_at', 'placement_questions_count', 'training_questions_count'
        ]
        read_only_fields = ['created_at', 'placement_questions_count', 'training_questions_count']


class ConceptStudentSerializer(serializers.ModelSerializer):
    # questions = QuestionStudentSerializer(many=True, read_only=True)

    class Meta:
        model = Concept
        fields = [
            'id', 'name', 'explanation', 'reference_title',
            'reference_url', 'reference_type',
        ]


# ─── Skill ────────────────────────────────────────────────────────────────────

class SkillSerializer(serializers.ModelSerializer):
    # placement_questions = PlacementQuestionSerializer(many=True, read_only=True)
    # lessons = LessonSerializer(many=True, read_only=True)

    class Meta:
        model = Skill
        fields = [
            'id', 'subject', 'name', 'description',
            'is_active', 'created_at',
            'placement_num_concepts', 'placement_total_questions', 'training_beginner_count',
            'training_intermediate_count', 'training_advanced_count',
        ]
        read_only_fields = ['subject', 'created_at']

    def validate(self, data):
        num_concepts = data.get(
            'placement_num_concepts',
            getattr(self.instance, 'placement_num_concepts', None)
        )
        total_questions = data.get(
            'placement_total_questions',
            getattr(self.instance, 'placement_total_questions', None)
        )

        if num_concepts is not None and total_questions is not None:
            if num_concepts < 1:
                raise serializers.ValidationError(
                    'عدد المفاهيم لا يجب ان يقل عن 1'
                )
            if total_questions < 1:
                raise serializers.ValidationError(
                    'عدد الاسئلة لا يجب ان يكون 0'
                )

            divisor = num_concepts * 3    
            if total_questions % divisor != 0:
                raise serializers.ValidationError(
                    f'عدد الأسئلة يجب أن يكون من مضاعفات {divisor}'
                )
            
        beginner = data.get(
            'training_beginner_count',
            getattr(self.instance, 'training_beginner_count', None)
        )
        intermediate = data.get(
            'training_intermediate_count',
            getattr(self.instance, 'training_intermediate_count', None)
        )
        advanced = data.get(
            'training_advanced_count',
            getattr(self.instance, 'training_advanced_count', None)
        )

        total_training = (beginner or 0) + (intermediate or 0) + (advanced or 0)
        if total_training < 1:
            raise serializers.ValidationError(
                'يجب أن يحتوي التدريب على سؤال واحد على الأقل'
            )

        return data


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



# ─── Channel ──────────────────────────────────────────────────────────────

class ChannelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Channel
        fields = [
            'id', 'name', 'description',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class ChannelStudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Channel
        fields = ['id', 'name', 'description', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class ChannelMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChannelMessage
        fields = [
            'id', 'message_type', 'text_content',
            'file', 'is_section', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class ChannelMessageStudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChannelMessage
        fields = [
            'id', 'message_type', 'text_content',
            'file', 'is_section', 'created_at', 'updated_at'
        ]

        read_only_fields = ['created_at', 'updated_at']
