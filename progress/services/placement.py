"""Placement session workflow: building sessions, grading submissions,
updating learner/domain profiles and resetting progress.
"""

import random
from collections import defaultdict

from django.db import transaction
from django.db.models import F, OuterRef, Subquery
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from content.models import Concept, PlacementQuestion

from ..constants import (
    ASSESSMENT_REASSESS_COOLDOWN,
    LEVEL_VALUES,
    PLACEMENT_XP_BY_LEVEL,
    SKILL_MASTERY_SCORE,
    SMOOTHING_SIZEABLE_DIFF,
    WEIGHT_NEW_SMOOTHED,
    WEIGHT_NEW_STABLE,
    WEIGHT_OLD_SMOOTHED,
    WEIGHT_OLD_STABLE,
)
from ..models import (
    PlacementAnswer,
    PlacementQuestionHistory,
    PlacementSession,
    PlacementSessionQuestion,
    UserConceptProfile,
    UserSkillProfile,
)
from .common import (
    answers_match,
    calculate_concept_status,
    derive_level_from_score,
    least_known_concepts,
    pct,
)


# ─────────────────────────────── session building ─────────────────────────────

def build_placement_session(user, skill):
    """Create an unanswered placement session for the given skill.

    Returns (session, error); exactly one of them is None.
    """
    profile = (
        UserSkillProfile.objects.filter(user=user, skill=skill)
        .only('can_reassess_at')
        .first()
    )

    if profile and profile.can_reassess_at and timezone.now() < profile.can_reassess_at:
        remaining = profile.can_reassess_at - timezone.now()
        hours = int(remaining.total_seconds() // 3600)
        return None, {
            'detail': f'Please wait {hours} hours before reassessment',
            'can_reassess_at': profile.can_reassess_at,
        }

    num_concepts = skill.placement_num_concepts
    total_questions = skill.placement_total_questions
    per_level = total_questions // (num_concepts * 3)

    concepts = list(Concept.objects.filter(skill=skill, is_active=True))

    counts_map = {
        row['concept_id']: row
        for row in PlacementQuestion.objects.concept_level_counts(concepts)
    }

    valid_concepts = []
    for concept in concepts:
        row = counts_map.get(concept.id)
        if row is None:
            continue
        if (
            row['beginner_count'] >= per_level
            and row['intermediate_count'] >= per_level
            and row['advanced_count'] >= per_level
        ):
            valid_concepts.append(concept)

    if len(valid_concepts) < num_concepts:
        return None, {'detail': 'Not enough complete concepts to start the assessment'}

    selected_concepts = least_known_concepts(user, valid_concepts)[:num_concepts]

    candidates = list(
        PlacementQuestion.objects.filter(
            concept__in=selected_concepts,
            is_active=True,
        )
        .annotate(
            times_seen=Subquery(
                PlacementQuestionHistory.objects.filter(
                    user=user,
                    question=OuterRef('pk'),
                ).values('times_seen')[:1]
            )
        )
        .order_by(
            'concept_id',
            'level',
            F('times_seen').asc(nulls_first=True),
        )
    )

    grouped = defaultdict(list)
    for question in candidates:
        grouped[(question.concept_id, question.level)].append(question)

    questions_by_level = {level: [] for level in LEVEL_VALUES}
    for concept in selected_concepts:
        for level in LEVEL_VALUES:
            level_questions = grouped.get((concept.id, level), [])
            if len(level_questions) < per_level:
                return None, {'detail': 'Not enough available questions'}
            questions_by_level[level].extend(level_questions[:per_level])

    questions = []
    for level in LEVEL_VALUES:
        random.shuffle(questions_by_level[level])
        questions.extend(questions_by_level[level])

    if not questions:
        return None, {'detail': 'No questions available'}

    with transaction.atomic():
        session = PlacementSession.objects.create(user=user, skill=skill)
        PlacementSessionQuestion.objects.bulk_create([
            PlacementSessionQuestion(session=session, question=q, order=idx)
            for idx, q in enumerate(questions)
        ])

    return session, None


# ────────────────────────────── grading / persisting ──────────────────────────

def calculate_and_save_result(session, answers_data):
    """Grade a placement submission and persist every side effect atomically.

    answers_data: list of {'question_id': int, 'user_answer': str}
    """
    session_questions = list(
        session.session_questions.select_related('question__concept').order_by('order')
    )
    questions_by_id = {sq.question_id: sq.question for sq in session_questions}
    session_qids = set(questions_by_id)

    for item in answers_data:
        if item['question_id'] not in session_qids:
            raise ValidationError(f"Question {item['question_id']} does not belong to this session")

    answered = {item['question_id']: item['user_answer'] for item in answers_data}
    answered.update({qid: '' for qid in session_qids if qid not in answered})

    with transaction.atomic():
        locked = (
            PlacementSession.objects.select_for_update()
            .filter(pk=session.pk, completed_at__isnull=True)
            .first()
        )
        if locked is None:
            raise ValidationError('Session not found or expired')

        _persist_answers_and_history(session, answered, questions_by_id)
        score, level, xp_earned, by_diff, concept_stats = _grade(answered, questions_by_id)
        _update_concept_profiles(session.user, concept_stats)
        weak_concepts = [
            {'id': cid, 'name': stats['name']}
            for cid, stats in concept_stats.items()
            if stats['status'] == 'weak'
        ]
        profile = _update_skill_profile(session, score, level, xp_earned, weak_concepts)
        session.score = score
        session.level_result = level
        session.completed_at = timezone.now()
        session.result = _build_result_payload(
            session_questions, answered, questions_by_id,
            score, level, xp_earned, by_diff, concept_stats, profile,
        )
        session.save(update_fields=['score', 'level_result', 'completed_at', 'result'])

    return session.result


def _persist_answers_and_history(session, answered, questions_by_id):
    """Bulk-write answers and question history (no per-row queries)."""
    history_rows = {
        h.question_id: h
        for h in PlacementQuestionHistory.objects.filter(
            user=session.user,
            question_id__in=list(answered),
        )
    }
    histories_to_update = []
    histories_to_create = []

    def is_correct(qid, user_answer):
        question = questions_by_id[qid]
        return answers_match(
            user_answer,
            question.correct_answer,
            question.question_type,
        )

    PlacementAnswer.objects.bulk_create([
        PlacementAnswer(
            session=session,
            question_id=qid,
            user_answer=user_answer,
            is_correct=is_correct(qid, user_answer),
        )
        for qid, user_answer in answered.items()
    ])

    for qid, user_answer in answered.items():
        was_correct = is_correct(qid, user_answer)
        history = history_rows.get(qid)
        if history:
            history.times_seen += 1
            if was_correct:
                history.times_correct += 1
            history.last_result = 'correct' if was_correct else 'wrong'
            histories_to_update.append(history)
        else:
            histories_to_create.append(PlacementQuestionHistory(
                user=session.user,
                question_id=qid,
                times_seen=1,
                times_correct=1 if was_correct else 0,
                last_result='correct' if was_correct else 'wrong',
            ))

    if histories_to_update:
        PlacementQuestionHistory.objects.bulk_update(
            histories_to_update, ['times_seen', 'times_correct', 'last_result']
        )
    if histories_to_create:
        PlacementQuestionHistory.objects.bulk_create(histories_to_create)


def _grade(answered, questions_by_id):
    """Score the submission in memory; no database round-trips."""
    by_diff = {level: [] for level in LEVEL_VALUES}
    concept_results = defaultdict(list)
    concept_names = {}
    xp_earned = 0

    for qid, user_answer in answered.items():
        question = questions_by_id[qid]
        is_correct = answers_match(
            user_answer,
            question.correct_answer,
            question.question_type,
        )
        by_diff[question.level].append(is_correct)
        concept_results[question.concept_id].append(is_correct)
        concept_names[question.concept_id] = question.concept.name
        if is_correct:
            xp_earned += PLACEMENT_XP_BY_LEVEL[question.level]

    b_score = pct(by_diff['beginner'])
    i_score = pct(by_diff['intermediate'])
    a_score = pct(by_diff['advanced'])

    if b_score >= 80 and i_score >= 60 and a_score >= 40:
        level = 'advanced'
    elif b_score >= 60 and i_score >= 30:
        level = 'intermediate'
    else:
        level = 'beginner'

    total_correct = sum(
        1 for results in concept_results.values() for r in results if r
    )
    total = len(answered)
    score = round(total_correct / total * 100) if total else 0

    concept_stats = {}
    for cid, results in concept_results.items():
        concept_score = pct(results)
        new_avg, new_status = calculate_concept_status(None, concept_score)
        concept_stats[cid] = {
            'score': concept_score,
            'avg': new_avg,
            'status': new_status,
            'results': results,
            'name': concept_names[cid],
        }

    return score, level, xp_earned, by_diff, concept_stats


def _update_concept_profiles(user, concept_stats):
    """Bulk-update/create UserConceptProfile rows for the assessed concepts."""
    profiles = {
        p.concept_id: p
        for p in UserConceptProfile.objects.filter(
            user=user,
            concept_id__in=concept_stats,
        )
    }
    to_update = []
    to_create = []

    for cid, stats in concept_stats.items():
        previous_avg = profiles[cid].avg_score if cid in profiles else None
        new_avg, new_status = calculate_concept_status(previous_avg, stats['score'])

        profile = profiles.get(cid)
        if profile:
            profile.avg_score = new_avg
            profile.times_trained += 1
            profile.status = new_status
            profile.updated_at = timezone.now()
            to_update.append(profile)
        else:
            to_create.append(UserConceptProfile(
                user=user,
                concept_id=cid,
                avg_score=new_avg,
                times_trained=1,
                status=new_status,
            ))

    if to_update:
        UserConceptProfile.objects.bulk_update(
            to_update, ['avg_score', 'times_trained', 'status', 'updated_at']
        )
    if to_create:
        UserConceptProfile.objects.bulk_create(to_create)


def _update_skill_profile(session, score, level, xp_earned, weak_concepts):
    """Update the user's skill profile, applying smoothing + mastery rules."""
    profile, _ = UserSkillProfile.objects.get_or_create(
        user=session.user,
        skill=session.skill,
    )

    previous = profile.assessment_score

    if profile.total_assessments == 0:
        new_score = score
    else:
        diff = abs(score - previous)
        if diff >= SMOOTHING_SIZEABLE_DIFF:
            new_score = (previous * WEIGHT_OLD_SMOOTHED) + (score * WEIGHT_NEW_SMOOTHED)
        else:
            new_score = (previous * WEIGHT_OLD_STABLE) + (score * WEIGHT_NEW_STABLE)

    profile.current_level = derive_level_from_score(new_score)
    profile.assessment_score = new_score
    profile.total_assessments += 1
    profile.last_assessed_at = timezone.now()
    profile.can_reassess_at = timezone.now() + ASSESSMENT_REASSESS_COOLDOWN
    profile.xp_total += xp_earned

    is_mastered = (
        level == 'advanced'
        and new_score >= SKILL_MASTERY_SCORE
        and not weak_concepts
        and profile.total_assessments >= 3
    )
    if is_mastered:
        profile.is_mastered = True
        profile.mastered_at = timezone.now()

    profile.save()
    return profile


# ─────────────────────────────── result payload ──────────────────────────────

def _build_result_payload(
    session_questions, answered, questions_by_id,
    score, level, xp_earned, by_diff, concept_stats, profile,
):
    weak_concepts = [
        {'id': cid, 'name': stats['name']}
        for cid, stats in concept_stats.items()
        if stats['status'] == 'weak'
    ]

    return {
        'score': score,
        'level': level,
        'correct_count': sum(1 for stats in concept_stats.values() for r in stats['results'] if r),
        'total_count': len(answered),
        'by_difficulty': {
            diff: {
                'correct': sum(by_diff[diff]),
                'total': len(by_diff[diff]),
                'score': pct(by_diff[diff]),
            }
            for diff in LEVEL_VALUES
        },
        'by_concept': [
            {
                'concept_id': cid,
                'concept_name': stats['name'],
                'score': stats['score'],
                'status': stats['status'],
            }
            for cid, stats in concept_stats.items()
        ],
        'weak_concepts': weak_concepts,
        'can_reassess_at': profile.can_reassess_at.isoformat(),
        'xp_earned': xp_earned,
        'questions_review': [
            {
                'question_id': sq.question.id,
                'question': sq.question.question,
                'user_answer': answered[sq.question_id],
                'correct_answer': sq.question.correct_answer,
                'is_correct': answers_match(
                    answered[sq.question_id],
                    sq.question.correct_answer,
                    sq.question.question_type,
                ),
                'level_question': sq.question.level,
                'concept_name': sq.question.concept.name,
            }
            for sq in session_questions
        ],
    }


def reset_skill_progress(user, skill):
    """Wipe every trace of a user's progress for the given skill."""
    with transaction.atomic():
        PlacementSession.objects.filter(user=user, skill=skill).delete()
        UserConceptProfile.objects.filter(
            user=user,
            concept__skill=skill,
        ).delete()
        UserSkillProfile.objects.filter(user=user, skill=skill).delete()