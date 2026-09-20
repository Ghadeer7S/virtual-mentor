"""Regression guard against accidental N+1 / extra queries.

Counts the *business* SQL statements (SAVEPOINT bookkeeping from nested
atomic blocks is excluded) executed by the critical paths. Any future
refactor that leaks queries breaks these tests on purpose, and the failure
message prints the violating SQL for an easy diff.
"""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from types import SimpleNamespace

from progress.services.placement import (
    build_placement_session,
    calculate_and_save_result,
)
from progress.services.training import (
    build_training_session,
    complete_training_session,
    submit_training_answer,
)
from progress.tests._factories import (
    make_concept,
    make_placement_question,
    make_skill,
    make_training_question,
)
from progress.views import PlacementSessionHistoryViewSet, TrainingSessionHistoryViewSet


def run_queries(func):
    with CaptureQueriesContext(connection) as captured:
        func()
    return [entry['sql'] for entry in captured]


def business_queries(sqls):
    return [
        sql for sql in sqls
        if 'SAVEPOINT' not in sql.upper() and 'RELEASE SAVEPOINT' not in sql.upper()
    ]


def assert_business_queries(expected, func):
    sqls = business_queries(run_queries(func))
    assert len(sqls) == expected, (
        f'expected {expected} business queries, got {len(sqls)}:\n'
        + '\n'.join(sqls)
    )


def make_placement_skill():
    skill = make_skill(num_concepts=1, total_questions=3)
    concept = make_concept(skill, 'C')
    make_placement_question(concept, 'beginner', 'b')
    make_placement_question(concept, 'intermediate', 'i')
    make_placement_question(concept, 'advanced', 'a')
    return skill


def placement_session(user, skill):
    session, error = build_placement_session(user, skill)
    assert error is None, error
    return session


# ─────────────────────────────── placement ───────────────────────────────

@pytest.mark.django_db
def test_build_placement_session_stays_single_backed(user):
    skill = make_placement_skill()
    assert_business_queries(
        7,
        lambda: build_placement_session(user, skill),
    )


@pytest.mark.django_db
def test_placement_submit_stays_bounded(user):
    skill = make_placement_skill()
    session = placement_session(user, skill)
    data = [
        {'question_id': q.question_id, 'user_answer': q.question.level[0]}
        for q in session.session_questions.all()
    ]
    assert_business_queries(
        11,
        lambda: calculate_and_save_result(session, data),
    )


@pytest.mark.django_db
def test_placement_history_list_is_single_query(user):
    skill = make_placement_skill()
    correct = {'beginner': 'b', 'intermediate': 'i', 'advanced': 'a'}
    for _ in range(3):
        session = placement_session(user, skill)
        data = [
            {
                'question_id': q.question_id,
                'user_answer': correct[q.question.level],
            }
            for q in session.session_questions.all()
        ]
        calculate_and_save_result(session, data)

        profile = user.skill_profiles.get(skill=skill)
        profile.can_reassess_at = None
        profile.save(update_fields=['can_reassess_at'])

    view = PlacementSessionHistoryViewSet()
    view.request = SimpleNamespace(user=user)
    assert_business_queries(1, lambda: list(view.get_queryset()))


# ─────────────────────────────── training ───────────────────────────────

def make_training_data(plan=(1, 0, 0), count=1):
    skill = make_skill(num_concepts=1, total_questions=3, training=plan)
    concept = make_concept(skill, 'C')
    questions = [
        make_training_question(concept, 'beginner', f't{i}')
        for i in range(count)
    ]
    return skill, concept, questions


def training_session(user, skill, concept):
    session, error = build_training_session(user, skill, mode='manual', concept=concept)
    assert error is None, error
    return session


@pytest.mark.django_db
def test_training_submit_stays_bounded(user):
    skill, concept, questions = make_training_data(plan=(2, 0, 0), count=2)
    session = training_session(user, skill, concept)
    assert_business_queries(
        9,
        lambda: submit_training_answer(session, questions[0].id, 't0'),
    )


@pytest.mark.django_db
def test_training_complete_stays_bounded(user):
    skill, concept, (q,) = make_training_data()
    session = training_session(user, skill, concept)
    submit_training_answer(session, q.id, 't0')
    assert_business_queries(6, lambda: complete_training_session(session))


@pytest.mark.django_db
def test_training_history_list_is_single_query(user):
    skill, concept, (q,) = make_training_data()
    for _ in range(3):
        session = training_session(user, skill, concept)
        submit_training_answer(session, q.id, 't0')
        complete_training_session(session)

    view = TrainingSessionHistoryViewSet()
    view.request = SimpleNamespace(user=user)
    assert_business_queries(1, lambda: list(view.get_queryset()))