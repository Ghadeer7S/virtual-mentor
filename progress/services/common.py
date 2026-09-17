"""Pure helpers shared across the placement / training domains."""

import re

from ..constants import (
    CONCEPT_IMPROVING,
    CONCEPT_STRONG,
    SCORE_ADVANCED,
    SCORE_INTERMEDIATE,
    STATUS_PRIORITY,
    WEIGHT_NEW_AVERAGE,
    WEIGHT_OLD_AVERAGE,
)
from ..models import UserConceptProfile

# Arabic diacritics (tashkeel) + tatweel that should not affect the answer.
_ARABIC_FORMS = re.compile(r'[\u064b-\u065f\u0670\u0640]')
_WHITESPACE = re.compile(r'\s+')


def normalize_arabic(text):
    """Trim, collapse whitespace and strip Arabic diacritics/tatweel."""
    if not text:
        return ''
    text = _WHITESPACE.sub(' ', text.strip())
    return _ARABIC_FORMS.sub('', text)


def _normalize_fill(text):
    """Aggressive normalization for fill-in-the-blank answers."""
    text = normalize_arabic(text)
    if text.startswith('ال') and len(text) > 2:
        text = text[2:]
    return text.lower()


def answers_match(answer, correct, question_type):
    """Type-aware comparison of a user answer against the correct one.

    fill_blank/ordering -> normalize tashkeel, "ال", case and spacing.
    multiple_choice/true_false -> trimmed exact comparison (options are literal).
    """
    answer = answer or ''
    correct = correct or ''
    if question_type in ('fill_blank', 'ordering'):
        return _normalize_fill(answer) == _normalize_fill(correct)
    return answer.strip() == correct.strip()


def pct(values):
    """Percentage of truthy items, rounded to the nearest integer."""
    if not values:
        return 0
    return round(sum(bool(v) for v in values) / len(values) * 100)


def derive_level_from_score(score):
    if score >= SCORE_ADVANCED:
        return 'advanced'
    if score >= SCORE_INTERMEDIATE:
        return 'intermediate'
    return 'beginner'


def calculate_concept_status(old_avg, concept_score):
    """Return (new_avg, status) combining history with the latest result."""
    if old_avg:
        new_avg = (old_avg * WEIGHT_OLD_AVERAGE) + (concept_score * WEIGHT_NEW_AVERAGE)
    else:
        new_avg = concept_score

    if new_avg >= CONCEPT_STRONG:
        status = 'strong'
    elif new_avg >= CONCEPT_IMPROVING:
        status = 'improving'
    else:
        status = 'weak'

    return new_avg, status


def least_known_concepts(user, concepts):
    """Order concepts weakest-first for session building.

    Single profile query regardless of how many concepts are passed.
    Ties keep their original ordering (stable sort).
    """
    concepts = list(concepts)
    profiles = {
        p.concept_id: p
        for p in UserConceptProfile.objects.filter(
            user=user,
            concept_id__in=[c.id for c in concepts],
        )
    }

    def key(concept):
        profile = profiles.get(concept.id)
        status = profile.status if profile else 'not_started'
        times_trained = profile.times_trained if profile else 0
        order = concept.order if concept.order is not None else concept.id
        return STATUS_PRIORITY[status], times_trained, order

    return sorted(concepts, key=key)