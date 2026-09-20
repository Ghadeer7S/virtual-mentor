"""Test factories (not a pytest test module)."""

from content.models import (
    Category,
    Concept,
    PlacementQuestion,
    Skill,
    Subject,
    TrainingQuestion,
)


def make_skill(num_concepts=1, total_questions=3, training=(0, 0, 0)):
    category = Category.objects.create(name='Category')
    subject = Subject.objects.create(category=category, name='Subject')
    return Skill.objects.create(
        subject=subject,
        name='Skill',
        placement_num_concepts=num_concepts,
        placement_total_questions=total_questions,
        training_beginner_count=training[0],
        training_intermediate_count=training[1],
        training_advanced_count=training[2],
    )


def make_concept(skill, name='Concept', order=0):
    return Concept.objects.create(
        skill=skill, name=name, explanation='exp', order=order,
    )


def make_placement_question(concept, level, correct, order=0):
    return PlacementQuestion.objects.create(
        skill=concept.skill,
        concept=concept,
        level=level,
        question_type='fill_blank',
        question=f'{level} placement question',
        correct_answer=correct,
        order=order,
    )


def make_training_question(concept, level, correct):
    return TrainingQuestion.objects.create(
        concept=concept,
        level=level,
        question_type='fill_blank',
        question=f'{level} training question',
        correct_answer=correct,
        explanation='explanation',
    )