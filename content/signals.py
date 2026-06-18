from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from django.db.models import F

from .models import (
    PlacementQuestion,
    TrainingQuestion,
    Concept
)


# =========================================================
# PlacementQuestion Signals
# =========================================================

@receiver(pre_save, sender=PlacementQuestion)
def placement_question_pre_save(sender, instance, **kwargs):

    if not instance.pk:
        return

    previous = PlacementQuestion.objects.get(pk=instance.pk)

    if previous.concept_id != instance.concept_id:

        Concept.objects.filter(
            id=previous.concept_id
        ).update(
            placement_questions_count=F('placement_questions_count') - 1
        )

        Concept.objects.filter(
            id=instance.concept_id
        ).update(
            placement_questions_count=F('placement_questions_count') + 1
        )


@receiver(post_save, sender=PlacementQuestion)
def placement_question_post_save(sender, instance, created, **kwargs):

    if created:
        Concept.objects.filter(
            id=instance.concept_id
        ).update(
            placement_questions_count=F('placement_questions_count') + 1
        )


@receiver(post_delete, sender=PlacementQuestion)
def placement_question_post_delete(sender, instance, **kwargs):

    Concept.objects.filter(
        id=instance.concept_id
    ).update(
        placement_questions_count=F('placement_questions_count') - 1
    )


# =========================================================
# TrainingQuestion Signals
# =========================================================

@receiver(pre_save, sender=TrainingQuestion)
def training_question_pre_save(sender, instance, **kwargs):

    if not instance.pk:
        return

    previous = TrainingQuestion.objects.get(pk=instance.pk)

    if previous.concept_id != instance.concept_id:

        Concept.objects.filter(
            id=previous.concept_id
        ).update(
            training_questions_count=F('training_questions_count') - 1
        )

        Concept.objects.filter(
            id=instance.concept_id
        ).update(
            training_questions_count=F('training_questions_count') + 1
        )


@receiver(post_save, sender=TrainingQuestion)
def training_question_post_save(sender, instance, created, **kwargs):

    if created:
        Concept.objects.filter(
            id=instance.concept_id
        ).update(
            training_questions_count=F('training_questions_count') + 1
        )


@receiver(post_delete, sender=TrainingQuestion)
def training_question_post_delete(sender, instance, **kwargs):

    Concept.objects.filter(
        id=instance.concept_id
    ).update(
        training_questions_count=F('training_questions_count') - 1
    )