from django.db import models
from django.conf import settings
from content.models import Skill, Concept, PlacementQuestion, TrainingQuestion


class UserSkillProfile(models.Model):
    LEVEL_CHOICES = [
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
    ]

    user              = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='skill_profiles')
    skill             = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name='user_profiles')
    current_level     = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='beginner')
    assessment_score  = models.FloatField(default=0)
    is_mastered       = models.BooleanField(default=False)
    mastered_at       = models.DateTimeField(null=True, blank=True)
    total_assessments = models.PositiveIntegerField(default=0)
    last_assessed_at  = models.DateTimeField(null=True, blank=True)
    can_reassess_at   = models.DateTimeField(null=True, blank=True)
    xp_total          = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ['user', 'skill']

    def __str__(self):
        return f"{self.user.email} | {self.skill.name} | {self.current_level}"


class UserConceptProfile(models.Model):
    STATUS_CHOICES = [
        ('not_started', 'Not Started'),
        ('weak', 'Weak'),
        ('improving', 'Improving'),
        ('strong', 'Strong'),
    ]

    user         = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='concept_profiles')
    concept      = models.ForeignKey(Concept, on_delete=models.CASCADE, related_name='user_profiles')
    status       = models.CharField(max_length=20, choices=STATUS_CHOICES, default='not_started')
    avg_score    = models.FloatField(default=0)
    times_trained = models.PositiveIntegerField(default=0)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'concept']

    def __str__(self):
        return f"{self.user.email} | {self.concept.name} | {self.status}"


class PlacementSession(models.Model):
    LEVEL_CHOICES = [
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
    ]

    user           = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='placement_sessions')
    skill          = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name='placement_sessions')
    score          = models.FloatField(null=True, blank=True)
    level_result   = models.CharField(max_length=20, choices=LEVEL_CHOICES, null=True, blank=True)
    started_at     = models.DateTimeField(auto_now_add=True)
    completed_at   = models.DateTimeField(null=True, blank=True)
    result = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.user.email} | {self.skill.name}"


class PlacementSessionQuestion(models.Model):
    session  = models.ForeignKey(PlacementSession, on_delete=models.CASCADE, related_name='session_questions')
    question = models.ForeignKey(PlacementQuestion, on_delete=models.CASCADE, related_name='session_questions')
    order    = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']
        unique_together = ['session', 'question']

    def __str__(self):
        return f"Session {self.session.id} | Q{self.order}"


class PlacementAnswer(models.Model):
    session    = models.ForeignKey(PlacementSession, on_delete=models.CASCADE, related_name='answers')
    question   = models.ForeignKey(PlacementQuestion, on_delete=models.CASCADE, related_name='answers')
    user_answer = models.CharField(max_length=255)
    is_correct  = models.BooleanField(default=False)

    class Meta:
        unique_together = ['session', 'question']

    def __str__(self):
        return f"Session {self.session.id} | {'✓' if self.is_correct else '✗'}"


class PlacementQuestionHistory(models.Model):
    RESULT_CHOICES = [
        ('correct', 'Correct'),
        ('wrong', 'Wrong'),
    ]

    user          = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='placement_question_histories')
    question      = models.ForeignKey(PlacementQuestion, on_delete=models.CASCADE, related_name='user_histories')
    times_seen    = models.PositiveIntegerField(default=0)
    times_correct = models.PositiveIntegerField(default=0)
    last_result   = models.CharField(max_length=10, choices=RESULT_CHOICES, blank=True)

    class Meta:
        unique_together = ['user', 'question']

    def __str__(self):
        return f"{self.user.email} | Q{self.question.id} | seen {self.times_seen}"
    

# ───── Training Session ──────────────────────────────────────────────────────
 
class TrainingSession(models.Model):
    MODE_CHOICES = [
        ('auto',   'Auto'),
        ('manual', 'Manual'),
    ]
 
    user         = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='training_sessions')
    skill        = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name='training_sessions')
    concept      = models.ForeignKey(Concept, on_delete=models.CASCADE, related_name='training_sessions')
    mode         = models.CharField(max_length=20, choices=MODE_CHOICES, default='manual')
    xp_earned       = models.PositiveIntegerField(default=0) 
    started_at   = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    result       = models.JSONField(null=True, blank=True)
 
    class Meta:
        ordering = ['-started_at']
 
    def __str__(self):
        return f"{self.user.email} | {self.concept.name} | {self.mode}"
 
 
class TrainingSessionQuestion(models.Model):
    session  = models.ForeignKey(TrainingSession, on_delete=models.CASCADE, related_name='session_questions')
    question = models.ForeignKey(TrainingQuestion, on_delete=models.CASCADE, related_name='session_questions')
    order    = models.PositiveIntegerField(default=0)
 
    class Meta:
        ordering        = ['order']
        unique_together = ['session', 'question']
 
    def __str__(self):
        return f"TrainingSession {self.session.id} | Q{self.order}"
 
 
class TrainingAnswer(models.Model):
    session     = models.ForeignKey(TrainingSession, on_delete=models.CASCADE, related_name='answers')
    question    = models.ForeignKey(TrainingQuestion, on_delete=models.CASCADE, related_name='answers')
    user_answer = models.TextField()
    is_correct  = models.BooleanField(default=False)
 
    class Meta:
        unique_together = ['session', 'question']
 
    def __str__(self):
        return f"TrainingSession {self.session.id} | {'✓' if self.is_correct else '✗'}"
 
class TrainingQuestionHistory(models.Model):
    RESULT_CHOICES = [
        ('correct', 'Correct'),
        ('wrong',   'Wrong'),
    ]

    user          = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='training_question_histories')
    question      = models.ForeignKey(TrainingQuestion, on_delete=models.CASCADE, related_name='user_histories')
    times_seen    = models.PositiveIntegerField(default=0)
    times_correct = models.PositiveIntegerField(default=0)
    last_result   = models.CharField(max_length=10, choices=RESULT_CHOICES, blank=True)

    class Meta:
        unique_together = ['user', 'question']

    def __str__(self):
        return f"{self.user.email} | Q{self.question.id} | seen {self.times_seen}"