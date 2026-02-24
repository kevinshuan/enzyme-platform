"""Commercial feasibility scorer.

Formula:
    difficulty        = mutation_count / max_mutation_threshold  → [0, 1]
    manufacturability = stability_score                          → [0, 1]
    feasibility_score = 0.5 * (1 - difficulty) + 0.5 * manufacturability

All outputs are clamped to [0.0, 1.0].
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.models import EnzymeCandidate

logger = logging.getLogger(__name__)

# Sub-score weights — named constants
_W_DIFFICULTY = 0.5
_W_MANUFACTURABILITY = 0.5


def score_feasibility(
    candidate: EnzymeCandidate,
    stability_score: float,
    max_mutation_threshold: int,
) -> float:
    """Compute commercial feasibility score in [0.0, 1.0].

    Higher score = easier to synthesise and manufacture.

    Args:
        candidate: EnzymeCandidate with mutation data.
        stability_score: Pre-computed stability sub-score from biological scorer.
        max_mutation_threshold: Maximum allowed mutations (from config).

    Returns:
        feasibility_score clamped to [0.0, 1.0].
    """
    difficulty = candidate.mutation_count / max(max_mutation_threshold, 1)
    difficulty = min(1.0, difficulty)  # cap at 1 in case of edge inputs

    manufacturability = stability_score

    feasibility_score = (
        _W_DIFFICULTY * (1.0 - difficulty)
        + _W_MANUFACTURABILITY * manufacturability
    )
    feasibility_score = max(0.0, min(1.0, feasibility_score))
    if not (0.0 <= feasibility_score <= 1.0):
        raise RuntimeError(f"feasibility_score out of range: {feasibility_score}")

    logger.info(
        '{"candidate_id": "%s", "stage": "feasibility", "input_values": '
        '{"difficulty": %.4f, "manufacturability": %.4f}, '
        '"output_score": %.4f, "timestamp": "%s"}',
        candidate.id,
        difficulty,
        manufacturability,
        feasibility_score,
        datetime.now(timezone.utc).isoformat(),
    )
    return feasibility_score
