"""Carbon impact scorer (simulation proxy).

Formula:
    efficiency_gain       = rng.uniform(0.9, 1.2)          # CO2 conversion proxy
    normalized_efficiency = (efficiency_gain - 0.9) / 0.3  # → [0, 1]
    deployment_factor     = stability_score                 # from biological scorer
    production_cost       = min(1.0, mutation_count * 0.01)
    raw                   = (normalized_efficiency * deployment_factor) - production_cost
    carbon_score          = (raw + 1.0) / 2.0              # rescale [-1,1] → [0,1]

All outputs are clamped to [0.0, 1.0].
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import numpy as np

from app.models import EnzymeCandidate

logger = logging.getLogger(__name__)

# Named constants — no magic numbers
_EFFICIENCY_MIN = 0.9   # lower bound of simulated efficiency gain
_EFFICIENCY_MAX = 1.2   # upper bound of simulated efficiency gain
_EFFICIENCY_RANGE = _EFFICIENCY_MAX - _EFFICIENCY_MIN  # 0.3
_PRODUCTION_COST_PER_MUTATION = 0.01


def score_carbon(
    candidate: EnzymeCandidate,
    stability_score: float,
    rng: np.random.Generator,
) -> float:
    """Compute carbon impact score in [0.0, 1.0].

    Higher score = greater estimated CO2 reduction potential.

    Args:
        candidate: EnzymeCandidate with mutation data.
        stability_score: Pre-computed stability sub-score from biological scorer.
        rng: Shared Generator — MUST be the same instance used for generation
             to guarantee byte-identical reproducibility (US3).

    Returns:
        carbon_score clamped to [0.0, 1.0].
    """
    efficiency_gain = float(rng.uniform(_EFFICIENCY_MIN, _EFFICIENCY_MAX))
    normalized_efficiency = (efficiency_gain - _EFFICIENCY_MIN) / _EFFICIENCY_RANGE

    deployment_factor = stability_score
    production_cost = min(1.0, candidate.mutation_count * _PRODUCTION_COST_PER_MUTATION)

    raw = (normalized_efficiency * deployment_factor) - production_cost
    # Rescale from [-1, 1] range to [0, 1]
    carbon_score = (raw + 1.0) / 2.0
    carbon_score = max(0.0, min(1.0, carbon_score))
    if not (0.0 <= carbon_score <= 1.0):
        raise RuntimeError(f"carbon_score out of range: {carbon_score}")

    logger.info(
        '{"candidate_id": "%s", "stage": "carbon", "input_values": '
        '{"efficiency_gain": %.4f, "deployment_factor": %.4f, "production_cost": %.4f}, '
        '"output_score": %.4f, "timestamp": "%s"}',
        candidate.id,
        efficiency_gain,
        deployment_factor,
        production_cost,
        carbon_score,
        datetime.now(timezone.utc).isoformat(),
    )
    return carbon_score
