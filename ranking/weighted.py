"""Weighted ranking engine with deterministic tie-breaking.

Sort order: final_score DESC, bio_score DESC on tie (per FR-008).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.models import EnzymeCandidate, ScoringWeights

logger = logging.getLogger(__name__)


def compute_final_score(candidate: EnzymeCandidate, weights: ScoringWeights) -> float:
    """Compute weighted final score from three dimension scores.

    Args:
        candidate: Fully scored EnzymeCandidate.
        weights: ScoringWeights with bio/carbon/feasibility weights.

    Returns:
        Weighted sum in [0.0, 1.0].
    """
    return (
        weights.bio_weight * (candidate.bio_score or 0.0)
        + weights.carbon_weight * (candidate.carbon_score or 0.0)
        + weights.feasibility_weight * (candidate.feasibility_score or 0.0)
    )


def rank_candidates(
    candidates: list[EnzymeCandidate],
    weights: ScoringWeights,
) -> list[EnzymeCandidate]:
    """Assign final scores and sort candidates.

    Primary sort:   final_score DESC
    Tie-break sort: bio_score DESC

    Args:
        candidates: List of fully scored EnzymeCandidate objects.
        weights: ScoringWeights to apply.

    Returns:
        Sorted list with final_score set on each candidate.
    """
    for candidate in candidates:
        candidate.final_score = compute_final_score(candidate, weights)

    ranked = sorted(
        candidates,
        key=lambda c: (c.final_score or 0.0, c.bio_score or 0.0),
        reverse=True,
    )

    top = ranked[0].final_score if ranked else 0.0
    bottom = ranked[-1].final_score if ranked else 0.0

    logger.info(
        '{"stage": "ranking", "total_candidates": %d, '
        '"top_score": %.4f, "bottom_score": %.4f, "timestamp": "%s"}',
        len(ranked),
        top,
        bottom,
        datetime.now(timezone.utc).isoformat(),
    )
    return ranked
