"""#2 Answer normalization: Arabic-aware answer matching.

Correctness of every placement/training answer flows through answers_match,
so its diacritic/ال/whitespace/case rules are unit-tested in isolation.
"""

import pytest

from progress.services.common import (
    answers_match,
    calculate_concept_status,
    derive_level_from_score,
    normalize_arabic,
    pct,
)


def test_normalize_strips_tashkeel_and_tatweel():
    assert normalize_arabic('كِتَابٌ') == 'كتاب'


def test_normalize_collapses_whitespace():
    assert normalize_arabic('  hello   world  ') == 'hello world'


def test_normalize_handles_none_and_empty():
    assert normalize_arabic(None) == ''
    assert normalize_arabic('') == ''


def test_fill_blank_ignores_tashkeel():
    assert answers_match('كِتَابُ العِلْمِ', 'كتاب العلم', 'fill_blank')


def test_fill_blank_strips_leading_al():
    assert answers_match('الكتاب', 'كتاب', 'fill_blank')


def test_fill_blank_is_case_and_spacing_insensitive():
    assert answers_match('  KITAB  ', 'kitab', 'fill_blank')


def test_fill_blank_detects_wrong_answer():
    assert not answers_match('قلم', 'كتاب', 'fill_blank')


def test_multiple_choice_is_literal_after_trim():
    assert answers_match('  A ', 'A', 'multiple_choice')
    assert not answers_match('a', 'A', 'multiple_choice')


def test_true_false_is_literal_after_trim():
    assert answers_match(' True ', 'True', 'true_false')
    assert not answers_match('true', 'True', 'true_false')


def test_ordering_ignores_tashkeel():
    assert answers_match('اجمعِ الارقَام معاً', 'اجمع الارقام معا', 'ordering')


def test_ordering_does_not_unify_hamza_forms():
    assert not answers_match('اجمع الارقام', 'اجمع الأرقام', 'ordering')


def test_none_answer_never_matches():
    assert not answers_match(None, 'كتاب', 'fill_blank')


def test_pct():
    assert pct([]) == 0
    assert pct([True, True]) == 100
    assert pct([True, False, False]) == 33


def test_derive_level_thresholds():
    assert derive_level_from_score(100) == 'advanced'
    assert derive_level_from_score(80) == 'advanced'
    assert derive_level_from_score(60) == 'intermediate'
    assert derive_level_from_score(59) == 'beginner'


def test_concept_status_thresholds_and_smoothing():
    new_avg, status = calculate_concept_status(None, 90)
    assert new_avg == pytest.approx(90)
    assert status == 'strong'

    _, status = calculate_concept_status(None, 55)
    assert status == 'improving'

    _, status = calculate_concept_status(None, 30)
    assert status == 'weak'

    new_avg, status = calculate_concept_status(80, 0)
    assert new_avg == pytest.approx(56)
    assert status == 'improving'