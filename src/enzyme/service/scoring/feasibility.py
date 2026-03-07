"""Commercial feasibility scorer — sequence-based, independent of thermodynamic stability."""
from __future__ import annotations

from datetime import datetime, timezone

from loguru import logger

from enzyme.models import EnzymeCandidate

_EXPRESSION_CHALLENGING_AA: frozenset[str] = frozenset("CW")
_MAX_CHALLENGING_FRACTION: float = 0.20

_W_DIFFICULTY = 0.5
_W_MANUFACTURABILITY = 0.5


def compute_manufacturability(sequence: str) -> float:
    """E. coli expression manufacturability proxy, normalised to [0.0, 1.0]."""
    challenging_fraction = (
        sum(1 for aa in sequence if aa in _EXPRESSION_CHALLENGING_AA) / len(sequence)
    )
    return max(0.0, 1.0 - challenging_fraction / _MAX_CHALLENGING_FRACTION)


def score_feasibility(
    candidate: EnzymeCandidate,
    max_mutation_threshold: int,
) -> float:
    """Compute commercial feasibility score in [0.0, 1.0]."""
    difficulty = candidate.mutation_count / max(max_mutation_threshold, 1)
    difficulty = min(1.0, difficulty)

    manufacturability = compute_manufacturability(candidate.mutated_sequence)

    feasibility_score = (
        _W_DIFFICULTY * (1.0 - difficulty)
        + _W_MANUFACTURABILITY * manufacturability
    )
    feasibility_score = max(0.0, min(1.0, feasibility_score))

    logger.info(
        '{{"candidate_id": "{}", "stage": "feasibility", "input_values": '
        '{{"difficulty": {:.4f}, "manufacturability": {:.4f}}}, '
        '"output_score": {:.4f}, "timestamp": "{}"}}',
        candidate.id,
        difficulty,
        manufacturability,
        feasibility_score,
        datetime.now(timezone.utc).isoformat(),
    )
    return feasibility_score
