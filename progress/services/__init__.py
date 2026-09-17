"""Services facade for the progress app.

Keeps the previous flat `progress.services` import surface intact while the
implementation lives in focused modules:

    progress/services/
        common.py    -> pure shared helpers
        placement.py -> placement session workflow
        training.py  -> training session workflow
        stats.py     -> progress statistics
"""

from .common import calculate_concept_status, derive_level_from_score
from .placement import (
    build_placement_session,
    calculate_and_save_result,
    reset_skill_progress,
)
from .stats import get_category_progress, get_progress_overview
from .training import (
    build_training_session,
    complete_training_session,
    get_valid_training_concepts,
    submit_training_answer,
)

__all__ = [
    'build_placement_session',
    'calculate_and_save_result',
    'reset_skill_progress',
    'build_training_session',
    'complete_training_session',
    'get_valid_training_concepts',
    'submit_training_answer',
    'get_category_progress',
    'get_progress_overview',
    'calculate_concept_status',
    'derive_level_from_score',
]