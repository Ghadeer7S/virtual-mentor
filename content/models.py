from django.db import models
from django.conf import settings


class Category(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon = models.ImageField(upload_to='icons/categories/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Subject(models.Model):
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name='subjects'
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon = models.ImageField(upload_to='icons/subjects/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)


    def __str__(self):
        return f"{self.category.name} - {self.name}"


class Skill(models.Model):
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name='skills'
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_skills'
    )

    def __str__(self):
        return f"{self.subject.name} - {self.name}"


class PlacementQuestion(models.Model):
    """أسئلة الامتحان التجريبي لتحديد مستوى الطالب"""

    LEVEL_CHOICES = [
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
    ]

    TYPE_CHOICES = [
        ('multiple_choice', 'Multiple Choice'),
        ('true_false', 'True / False'),
        ('fill_blank', 'Fill in the Blank'),
        ('ordering', 'Ordering'),
    ]

    skill = models.ForeignKey(
        Skill, on_delete=models.CASCADE, related_name='placement_questions'
    )
    question = models.TextField()
    question_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES)
    concept = models.ForeignKey(
        'Concept',
        on_delete=models.CASCADE,
        related_name='placement_questions'
    )
    options = models.JSONField(
        default=list,
        blank=True,
        help_text='For multiple_choice: ["option1", "option2", ...]'
    )
    correct_answer = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)


    def __str__(self):
        return f"{self.skill.name} | {self.level} | {self.concept}"


class Concept(models.Model):

    skill = models.ForeignKey(
        Skill,
        on_delete=models.CASCADE,
        related_name='concepts'
    )
    name = models.CharField(max_length=200)
    explanation = models.TextField()
    reference_title = models.CharField(max_length=100, blank=True)
    reference_url = models.URLField(blank=True)
    reference_type = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    placement_questions_count = models.PositiveIntegerField(default=0)
    training_questions_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']
        
    def __str__(self):
        return f"{self.skill.name} | {self.name}"
    


class TrainingQuestion(models.Model):
    LEVEL_CHOICES = [
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
    ]

    TYPE_CHOICES = [
        ('multiple_choice', 'Multiple Choice'),
        ('true_false', 'True / False'),
        ('fill_blank', 'Fill in the Blank'),
        ('ordering', 'Ordering'),
    ]

    concept = models.ForeignKey(
        Concept,
        on_delete=models.CASCADE,
        related_name='training_questions'
    )
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='beginner')
    question_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    question = models.TextField()
    options = models.JSONField(
        default=list,
        blank=True,
        help_text='للـ multiple_choice: ["خيار1", "خيار2", ...]'
    )
    correct_answer = models.TextField()
    explanation = models.TextField(
        help_text='يظهر للطالب بعد الإجابة دائماً'
    )
    hint = models.CharField(
        max_length=255,
        blank=True,
        help_text='يظهر عند طلب الطالب تلميحاً'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.concept.name} | {self.question_type}"



class Channel(models.Model):
    skill = models.ForeignKey(
        Skill, on_delete=models.CASCADE, related_name='channels'
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ChannelMessage(models.Model):
    TYPE_CHOICES = [
        ('text', 'Text'),
        ('audio', 'Audio'),
        ('image', 'Image'),
    ]

    channel = models.ForeignKey(
        Channel, on_delete=models.CASCADE, related_name='messages'
    )
    message_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    text_content = models.TextField(blank=True)
    file = models.FileField(upload_to='channels/messages/', blank=True, null=True)
    is_section = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']