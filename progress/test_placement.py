"""#1 Placement engine: session build, grading, level boundaries, smoothing,
cooldown, mastery and resubmission guards.
"""

import pytest
from rest_framework.exceptions import ValidationError

from progress._factories import (
    make_concept,
    make_placement_question,
    make_skill,
)
from progress.models import (
    PlacementAnswer,
    PlacementQuestionHistory,
    PlacementSession,
    UserConceptProfile,
    UserSkillProfile,
)
from progress.services.placement import (
    build_placement_session,
    calculate_and_save_result,
    reset_skill_progress,
)


def build(user, skill):
    session, error = build_placement_session(user, skill)
    assert error is None, error
    return session


def submit(session, by_level):
    data = [
        {'question_id': q.question_id, 'user_answer': by_level[q.question.level]}
        for q in session.session_questions.all()
    ]
    return calculate_and_save_result(session, data)


def allow_reassessment(user, skill):
    profile = UserSkillProfile.objects.get(user=user, skill=skill)
    profile.can_reassess_at = None
    profile.save(update_fields=['can_reassess_at'])


def make_three_question_skill():
    skill = make_skill(num_concepts=1, total_questions=3)
    concept = make_concept(skill, 'Concept')
    make_placement_question(concept, 'beginner', 'b')
    make_placement_question(concept, 'intermediate', 'i')
    make_placement_question(concept, 'advanced', 'a')
    return skill


@pytest.mark.django_db
def test_build_orders_questions_by_level(user):
    skill = make_three_question_skill()
    session = build(user, skill)
    levels = list(
        session.session_questions.values_list('question__level', flat=True)
    )
    assert levels == ['beginner', 'intermediate', 'advanced']


@pytest.mark.django_db
def test_build_rejects_when_concepts_are_missing(user):
    skill = make_skill(num_concepts=2, total_questions=6)
    concept = make_concept(skill, 'Only')
    make_placement_question(concept, 'beginner', 'b')
    make_placement_question(concept, 'intermediate', 'i')
    make_placement_question(concept, 'advanced', 'a')
    session, error = build_placement_session(user, skill)
    assert session is None
    assert 'Not enough complete concepts' in error['detail']


@pytest.mark.django_db
def test_all_correct_gives_advanced_and_xp(user):
    skill = make_three_question_skill()
    session = build(user, skill)
    result = submit(session, {'beginner': 'b', 'intermediate': 'i', 'advanced': 'a'})

    assert result['score'] == 100
    assert result['level'] == 'advanced'
    assert result['xp_earned'] == 10 + 15 + 25
    assert result['weak_concepts'] == []

    session = PlacementSession.objects.get(pk=session.pk)
    assert session.score == 100
    assert session.level_result == 'advanced'
    assert session.completed_at is not None

    profile = UserSkillProfile.objects.get(user=user, skill=skill)
    assert profile.assessment_score == 100
    assert profile.total_assessments == 1
    assert profile.current_level == 'advanced'
    assert profile.xp_total == 50
    assert profile.can_reassess_at is not None


@pytest.mark.django_db
def test_intermediate_boundary(user):
    skill = make_three_question_skill()
    session = build(user, skill)
    result = submit(
        session,
        {'beginner': 'b', 'intermediate': 'i', 'advanced': 'wrong'},
    )
    assert result['score'] == 67
    assert result['level'] == 'intermediate'


@pytest.mark.django_db
def test_all_wrong_gives_beginner_and_zero_xp(user):
    skill = make_three_question_skill()
    session = build(user, skill)
    result = submit(
        session,
        {'beginner': 'x', 'intermediate': 'x', 'advanced': 'x'},
    )
    assert result['score'] == 0
    assert result['level'] == 'beginner'
    assert result['xp_earned'] == 0


@pytest.mark.django_db
def test_answers_and_history_persisted(user):
    skill = make_three_question_skill()
    session = build(user, skill)
    submit(session, {'beginner': 'b', 'intermediate': 'wrong', 'advanced': 'a'})

    answers = PlacementAnswer.objects.filter(session=session)
    by_q = {a.question.level: a.is_correct for a in answers}
    assert by_q == {
        'beginner': True, 'intermediate': False, 'advanced': True,
    }

    histories = {
        h.question.level: h
        for h in PlacementQuestionHistory.objects.filter(user=user)
    }
    assert histories['beginner'].times_seen == 1
    assert histories['beginner'].times_correct == 1
    assert histories['beginner'].last_result == 'correct'
    assert histories['intermediate'].last_result == 'wrong'


@pytest.mark.django_db
def test_resubmission_is_rejected(user):
    skill = make_three_question_skill()
    session = build(user, skill)
    submit(session, {'beginner': 'b', 'intermediate': 'i', 'advanced': 'a'})

    data = [
        {'question_id': q.question_id, 'user_answer': 'b'}
        for q in session.session_questions.all()
    ]
    with pytest.raises(ValidationError):
        calculate_and_save_result(session, data)


@pytest.mark.django_db
def test_reassessment_obeys_cooldown(user):
    skill = make_three_question_skill()
    session = build(user, skill)
    submit(session, {'beginner': 'b', 'intermediate': 'i', 'advanced': 'a'})

    session, error = build_placement_session(user, skill)
    assert session is None
    assert 'Please wait' in error['detail']
    assert 'can_reassess_at' in error


@pytest.mark.django_db
def test_smoothing_on_large_drop(user):
    skill = make_three_question_skill()
    session = build(user, skill)
    submit(session, {'beginner': 'b', 'intermediate': 'i', 'advanced': 'a'})

    allow_reassessment(user, skill)
    session = build(user, skill)
    submit(session, {'beginner': 'x', 'intermediate': 'x', 'advanced': 'x'})

    profile = UserSkillProfile.objects.get(user=user, skill=skill)
    assert profile.assessment_score == pytest.approx(100 * 0.5 + 0 * 0.5)
    assert profile.total_assessments == 2
    assert profile.current_level == 'beginner'


@pytest.mark.django_db
def test_mastery_requires_three_advanced_assessments(user):
    skill = make_three_question_skill()
    correct = {'beginner': 'b', 'intermediate': 'i', 'advanced': 'a'}

    for _ in range(3):
        session = build(user, skill)
        submit(session, correct)
        allow_reassessment(user, skill)

    profile = UserSkillProfile.objects.get(user=user, skill=skill)
    assert profile.total_assessments == 3
    assert profile.is_mastered is True
    assert profile.mastered_at is not None
    assert profile.current_level == 'advanced'


@pytest.mark.django_db
def test_stable_smoothing_weights(user):
    skill = make_skill(num_concepts=1, total_questions=9)
    concept = make_concept(skill, 'Concept')
    for level in (
        'beginner', 'beginner', 'beginner',
        'intermediate', 'intermediate', 'intermediate',
        'advanced', 'advanced', 'advanced',
    ):
        make_placement_question(concept, level, level[0])

    session = build(user, skill)
    data = [
        {'question_id': q.question_id, 'user_answer': q.question.level[0]}
        for q in session.session_questions.all()[:8]
    ]
    calculate_and_save_result(session, data)
    assert (
        UserSkillProfile.objects.get(user=user, skill=skill).assessment_score
        == 89
    )

    allow_reassessment(user, skill)
    session = build(user, skill)
    data = [
        {'question_id': q.question_id, 'user_answer': q.question.level[0]}
        for q in session.session_questions.all()[:7]
    ]
    calculate_and_save_result(session, data)

    profile = UserSkillProfile.objects.get(user=user, skill=skill)
    assert profile.assessment_score == pytest.approx(89 * 0.7 + 78 * 0.3)
    assert profile.total_assessments == 2
    assert profile.current_level == 'advanced'


@pytest.mark.django_db
def test_reset_wipes_sessions_and_profiles(user):
    skill = make_three_question_skill()
    session = build(user, skill)
    submit(session, {'beginner': 'b', 'intermediate': 'i', 'advanced': 'a'})

    assert UserConceptProfile.objects.filter(user=user).exists()
    reset_skill_progress(user, skill)

    assert not PlacementSession.objects.filter(user=user).exists()
    assert not UserSkillProfile.objects.filter(user=user).exists()
    assert not UserConceptProfile.objects.filter(user=user).exists()