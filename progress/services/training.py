"""Training session workflow: readiness checks, session building,
per-answer submission with live XP, and completion summarising.
"""

import random
from collections import defaultdict

from django.db import transaction
from django.db.models import Count, F, OuterRef, Subquery
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from content.models import Concept, TrainingQuestion

from ..constants import LEVEL_VALUES, TRAINING_XP_BY_LEVEL
from ..models import (
    TrainingAnswer,
    TrainingQuestionHistory,
    TrainingSession,
    TrainingSessionQuestion,
    UserConceptProfile,
    UserSkillProfile,
)
from .common import answers_match, calculate_concept_status, least_known_concepts


def get_training_plan(skill):
    return {
        level: getattr(skill, 'training_%s_count' % level)
        for level in LEVEL_VALUES
    }


def get_valid_training_concepts(skill):
    """Concepts that have enough active questions per level.

    Built with a single aggregate query instead of 3x count per concept.
    """
    plan = get_training_plan(skill)

    counts = TrainingQuestion.objects.filter(
        concept__skill=skill,
        concept__is_active=True,
    ).values('concept_id', 'level').annotate(total=Count('id'))

    available = defaultdict(lambda: defaultdict(int))
    for row in counts:
        available[row['concept_id']][row['level']] = row['total']

    valid = []
    for concept in Concept.objects.filter(skill=skill, is_active=True):
        level_counts = available.get(concept.id, {})
        if (
            level_counts.get('beginner', 0) >= plan['beginner']
            and level_counts.get('intermediate', 0) >= plan['intermediate']
            and level_counts.get('advanced', 0) >= plan['advanced']
        ):
            valid.append(concept)

    return valid


def select_auto_training_concept(user, skill):
    valid_concepts = get_valid_training_concepts(skill)
    if not valid_concepts:
        return None
    return least_known_concepts(user, valid_concepts)[0]


def build_training_session(user, skill, mode='manual', concept=None):
    """Start a new training session for one manual / auto-selected concept."""
    if mode == 'auto':
        concept = select_auto_training_concept(user, skill)
        if not concept:
            return None, {'detail': 'لا يوجد مفهوم جاهز للتدريب حاليًا'}
    else:
        if not concept:
            return None, {'detail': 'يجب اختيار مفهوم في الوضع اليدوي'}
        valid_ids = {c.id for c in get_valid_training_concepts(skill)}
        if concept.id not in valid_ids:
            return None, {'detail': 'هذا المفهوم غير جاهز للتدريب بعد'}

    plan = get_training_plan(skill)

    candidates = list(
        TrainingQuestion.objects.filter(concept=concept)
        .annotate(
            times_seen=Subquery(
                TrainingQuestionHistory.objects.filter(
                    user=user,
                    question=OuterRef('pk'),
                ).values('times_seen')[:1]
            )
        )
        .order_by(F('times_seen').asc(nulls_first=True))
    )

    grouped = defaultdict(list)
    for question in candidates:
        grouped[question.level].append(question)

    questions = []
    for level, count in plan.items():
        selected = grouped.get(level, [])[:count]
        if len(selected) < count:
            return None, {'detail': 'عدد الأسئلة المتوفرة غير كافٍ لهذا المفهوم'}
        questions.extend(selected)

    random.shuffle(questions)

    with transaction.atomic():
        session = TrainingSession.objects.create(
            user=user, skill=skill, concept=concept, mode=mode
        )
        TrainingSessionQuestion.objects.bulk_create([
            TrainingSessionQuestion(session=session, question=q, order=idx)
            for idx, q in enumerate(questions)
        ])

    return session, None


def submit_training_answer(session, question_id, user_answer):
    """Grade a single training answer, awarding XP on first correct submit."""
    session_question = session.session_questions.filter(
        question_id=question_id
    ).select_related('question').first()

    if not session_question:
        raise ValidationError('السؤال لا ينتمي لهذه الجلسة')

    with transaction.atomic():
        locked = (
            TrainingSession.objects.select_for_update()
            .filter(pk=session.pk, completed_at__isnull=True)
            .first()
        )
        if locked is None:
            raise ValidationError('الجلسة غير موجودة أو منتهية')

        question = session_question.question
        is_correct = answers_match(
            user_answer,
            question.correct_answer,
            question.question_type,
        )

        answer, created = TrainingAnswer.objects.get_or_create(
            session=session,
            question=question,
            defaults={
                'user_answer': user_answer,
                'is_correct': is_correct,
            },
        )
        if not created:
            raise ValidationError('تم الإجابة على هذا السؤال مسبقًا')

        last_result = 'correct' if is_correct else 'wrong'
        updated = TrainingQuestionHistory.objects.filter(
            user=session.user,
            question=question,
        ).update(
            times_seen=F('times_seen') + 1,
            times_correct=F('times_correct') + (1 if is_correct else 0),
            last_result=last_result,
        )
        if not updated:
            TrainingQuestionHistory.objects.create(
                user=session.user,
                question=question,
                times_seen=1,
                times_correct=1 if is_correct else 0,
                last_result=last_result,
            )

        xp_earned = 0
        if is_correct:
            xp_earned = TRAINING_XP_BY_LEVEL.get(
                question.level, TRAINING_XP_BY_LEVEL['beginner']
            )
            session.xp_earned += xp_earned
            session.save(update_fields=['xp_earned'])

            profile_updated = UserSkillProfile.objects.filter(
                user=session.user,
                skill=session.skill,
            ).update(xp_total=F('xp_total') + xp_earned)
            if not profile_updated:
                UserSkillProfile.objects.create(
                    user=session.user,
                    skill=session.skill,
                    xp_total=xp_earned,
                )

    return {
        'question_id': question.id,
        'is_correct': is_correct,
        'correct_answer': question.correct_answer,
        'explanation': question.explanation,
        'xp_earned': xp_earned,
        'session_xp_total': session.xp_earned,
    }


def complete_training_session(session):
    """Finalise a session and roll its result into the concept profile.

    Unanswered questions are listed for review but do NOT count as wrong;
    the displayed score is based on answered questions only. The concept
    profile, however, is fed with the score weighted by coverage
    (answered / total), so a nearly-empty session can't inflate it.
    """
    if session.completed_at:
        return session.result

    with transaction.atomic():
        answers = list(
            session.answers.select_related('question').order_by('id')
        )
        answered_ids = {a.question_id for a in answers}
        unanswered = list(
            session.session_questions
            .exclude(question_id__in=answered_ids)
            .select_related('question')
            .order_by('order')
        )

        answered_count = len(answers)
        correct_count = sum(1 for a in answers if a.is_correct)
        wrong_count = answered_count - correct_count
        total = answered_count + len(unanswered)
        score = round(correct_count / answered_count * 100) if answered_count else 0
        coverage = round(answered_count / total * 100) if total else 0
        profile_score = round(score * coverage / 100) if answered_count else 0

        def serialize(question, user_answer=None, is_correct=None):
            payload = {
                'question_id': question.id,
                'question': question.question,
                'question_type': question.question_type,
                'level': question.level,
                'correct_answer': question.correct_answer,
                'explanation': question.explanation,
            }
            if user_answer is not None:
                payload['user_answer'] = user_answer
            if is_correct is not None:
                payload['is_correct'] = is_correct
            return payload

        if answered_count:
            _update_concept_profile(session, profile_score)

        session.completed_at = timezone.now()
        session.result = {
            'total_questions': total,
            'answered_questions_count': answered_count,
            'answered_questions': [
                serialize(a.question, user_answer=a.user_answer, is_correct=a.is_correct)
                for a in answers
            ],
            'correct_count': correct_count,
            'wrong_count': wrong_count,
            'xp_earned': session.xp_earned,
            'score': score,
            'coverage': coverage,
            'profile_score': profile_score,
            'wrong_questions': [
                serialize(a.question, user_answer=a.user_answer, is_correct=a.is_correct)
                for a in answers if not a.is_correct
            ],
            'unanswered_questions': [
                serialize(sq.question) for sq in unanswered
            ],
        }
        session.save()

    return session.result


def _update_concept_profile(session, concept_score):
    """Roll a completed training session into the user's concept profile.

    concept_score is already coverage-weighted by the caller, so partial
    sessions can't single-handedly inflate the profile.
    """
    profile, _ = UserConceptProfile.objects.get_or_create(
        user=session.user,
        concept=session.concept,
    )
    new_avg, new_status = calculate_concept_status(profile.avg_score, concept_score)
    profile.avg_score = new_avg
    profile.times_trained += 1
    profile.status = new_status
    profile.save(update_fields=['avg_score', 'times_trained', 'status', 'updated_at'])
    return profile