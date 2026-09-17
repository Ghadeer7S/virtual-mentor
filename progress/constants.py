"""Shared vocabulary and business rules for the progress domain.

Single source of truth for level/status choices, ordering priorities,
XP rewards, scoring thresholds and cooldowns so they can't drift apart
between models and services.
"""

from datetime import timedelta


# ───────────────────────────── domain vocabulary ─────────────────────────────

LEVELS = (
    ('beginner', 'Beginner'),
    ('intermediate', 'Intermediate'),
    ('advanced', 'Advanced'),
)

# Plain level keys derived from the canonical choices, so services never
# re-list the vocabulary.
LEVEL_VALUES = tuple(value for value, _ in LEVELS)

CONCEPT_STATUSES = (
    ('not_started', 'Not Started'),
    ('weak', 'Weak'),
    ('improving', 'Improving'),
    ('strong', 'Strong'),
)

ANSWER_RESULTS = (
    ('correct', 'Correct'),
    ('wrong', 'Wrong'),
)

# Weakest-first priority used when picking concepts for a session.
STATUS_PRIORITY = {
    'weak': 1,
    'improving': 2,
    'not_started': 3,
    'strong': 4,
}

# ───────────────────────────────── XP rules ──────────────────────────────────

PLACEMENT_XP_BY_LEVEL = {
    'beginner': 10,
    'intermediate': 15,
    'advanced': 25,
}

TRAINING_XP_BY_LEVEL = {
    'beginner': 5,
    'intermediate': 8,
    'advanced': 12,
}

# ────────────────────────────── scoring thresholds ───────────────────────────

SCORE_ADVANCED = 80
SCORE_INTERMEDIATE = 60

CONCEPT_STRONG = 70
CONCEPT_IMPROVING = 50

SKILL_IMPROVING_SCORE = 50
SKILL_MASTERY_SCORE = 85

# Assessed-score smoothing weights.
SMOOTHING_SIZEABLE_DIFF = 20
WEIGHT_OLD_SMOOTHED = 0.5
WEIGHT_NEW_SMOOTHED = 0.5
WEIGHT_OLD_STABLE = 0.7
WEIGHT_NEW_STABLE = 0.3

# Concept average smoothing weights.
WEIGHT_OLD_AVERAGE = 0.7
WEIGHT_NEW_AVERAGE = 0.3

# ──────────────────────────────── cooldowns ──────────────────────────────────

ASSESSMENT_REASSESS_COOLDOWN = timedelta(minutes=1)
STALE_SESSION_AGE = timedelta(hours=24)