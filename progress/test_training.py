"""#3 Coverage-weighted concept profile from training sessions.

The headline guarantee: a nearly-empty training session can't inflate the
concept profile, while a fully-attempted one feeds it honestly.
"""

import pytest
from rest_framework.exceptions import ValidationError

from progress._factories import (
    make_concept,
    make_skill,
    make_training_question,
)
from progress.models import UserSkillProfile
from progress.services.training import (
    build_training_session,
    complete_training_session,
    submit_training_answer,
)


def make_training_skill(*plan):
    skill = make_skill(num_concepts=1, total_questions=3, training=plan)
    concept = make_concept(skill, 'Concept')
    return skill, concept


@pytest.mark.django_db
def test_full_coverage_feeds_profile_honestly(user):
    skill, concept = make_training_skill(2, 0, 0)
    q1 = make_training_question(concept, 'beginner', 't1')
    q2 = make_training_question(concept, 'beginner', 't2')

    session, _ = build_training_session(user, skill, mode='manual', concept=concept)
    submit_training_answer(session, q1.id, 't1')
    submit_training_answer(session, q2.id, 't2')
    result = complete_training_session(session)

    assert result['score'] == 100
    assert result['coverage'] == 100
    assert result['profile_score'] == 100
    assert result['correct_count'] == 2
    assert result['wrong_count'] == 0

    profile = user.concept_profiles.get(concept=concept)
    assert profile.avg_score == 100
    assert profile.status == 'strong'
    assert profile.times_trained == 1


@pytest.mark.django_db
def test_partial_session_cannot_inflate_profile(user):
    skill, concept = make_training_skill(10, 0, 0)
    questions = [
        make_training_question(concept, 'beginner', f't{i}')
        for i in range(10)
    ]

    session, _ = build_training_session(user, skill, mode='manual', concept=concept)
    submit_training_answer(session, questions[0].id, 't0')
    result = complete_training_session(session)

    assert result['answered_questions_count'] == 1
    assert result['total_questions'] == 10
    assert result['score'] == 100
    assert result['coverage'] == 10
    assert result['profile_score'] == 10
    assert result['wrong_count'] == 0

    profile = user.concept_profiles.get(concept=concept)
    assert profile.avg_score == 10
    assert profile.status == 'weak'


@pytest.mark.django_db
def test_wrong_single_answer_keeps_profile_low(user):
    skill, concept = make_training_skill(10, 0, 0)
    questions = [
        make_training_question(concept, 'beginner', f'k{i}')
        for i in range(10)
    ]

    session, _ = build_training_session(user, skill, mode='manual', concept=concept)
    submit_training_answer(session, questions[0].id, 'not-the-answer')
    result = complete_training_session(session)

    assert result['score'] == 0
    assert result['coverage'] == 10
    assert result['profile_score'] == 0
    profile = user.concept_profiles.get(concept=concept)
    assert profile.status == 'weak'


@pytest.mark.django_db
def test_xp_scales_with_level(user):
    skill, concept = make_training_skill(1, 1, 1)
    questions = [
        make_training_question(concept, level, level[0])
        for level in ('beginner', 'intermediate', 'advanced')
    ]

    session, _ = build_training_session(user, skill, mode='manual', concept=concept)
    for question in questions:
        submit_training_answer(session, question.id, question.correct_answer)

    assert session.xp_earned == 5 + 8 + 12
    skill_profile = UserSkillProfile.objects.get(user=user, skill=skill)
    assert skill_profile.xp_total == 25


@pytest.mark.django_db
def test_duplicate_answer_is_rejected(user):
    skill, concept = make_training_skill(2, 0, 0)
    q1 = make_training_question(concept, 'beginner', 't1')
    make_training_question(concept, 'beginner', 't2')

    session, _ = build_training_session(user, skill, mode='manual', concept=concept)
    submit_training_answer(session, q1.id, 't1')
    with pytest.raises(ValidationError):
        submit_training_answer(session, q1.id, 't1')


@pytest.mark.django_db
def test_foreign_question_is_rejected(user):
    skill, concept = make_training_skill(2, 0, 0)
    make_training_question(concept, 'beginner', 't1')
    make_training_question(concept, 'beginner', 't2')

    session, _ = build_training_session(user, skill, mode='manual', concept=concept)
    with pytest.raises(ValidationError):
        submit_training_answer(session, 999999, 'x')


@pytest.mark.django_db
def test_completing_twice_is_idempotent(user):
    skill, concept = make_training_skill(1, 0, 0)
    q1 = make_training_question(concept, 'beginner', 't1')

    session, _ = build_training_session(user, skill, mode='manual', concept=concept)
    submit_training_answer(session, q1.id, 't1')
    assert complete_training_session(session) == complete_training_session(session)