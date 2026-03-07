"""Carbon impact scorer — deterministic, sequence-based efficiency proxy."""
from __future__ import annotations

from datetime import datetime, timezone

from loguru import logger

from enzyme.models import EnzymeCandidate

_POLAR_AA: frozenset[str] = frozenset("STNQDEKRHY")
_HIS_CHARGE_PH74: float = 0.09
_MAX_CHARGE_PER_RESIDUE: float = 0.5
_PRODUCTION_COST_PER_MUTATION: float = 0.01


def compute_polar_fraction(sequence: str) -> float:
    """Fraction of polar + charged residues in *sequence*. Returns [0.0, 1.0]."""
    return sum(1 for aa in sequence if aa in _POLAR_AA) / len(sequence)


def compute_charge_neutrality(sequence: str) -> float:
    """Proximity to electrical neutrality at pH 7.4, normalised to [0.0, 1.0]."""
    charge = (
        sum(1.0 for aa in sequence if aa in {"K", "R"})
        + sum(_HIS_CHARGE_PH74 for aa in sequence if aa == "H")
        - sum(1.0 for aa in sequence if aa in {"D", "E"})
    )
    per_residue = charge / len(sequence)
    return max(0.0, 1.0 - abs(per_residue) / _MAX_CHARGE_PER_RESIDUE)


def compute_co2_efficiency(sequence: str) -> float:
    """CO₂ conversion efficiency proxy in [0.0, 1.0], deterministic from sequence."""
    return (compute_polar_fraction(sequence) + compute_charge_neutrality(sequence)) / 2.0


def score_carbon(
    candidate: EnzymeCandidate,
    stability_score: float,
) -> float:
    """Compute carbon impact score in [0.0, 1.0]."""
    co2_efficiency = compute_co2_efficiency(candidate.mutated_sequence)
    deployment_factor = stability_score
    production_cost = min(1.0, candidate.mutation_count * _PRODUCTION_COST_PER_MUTATION)

    raw = (co2_efficiency * deployment_factor) - production_cost
    carbon_score = (raw + 1.0) / 2.0
    carbon_score = max(0.0, min(1.0, carbon_score))

    logger.info(
        '{{"candidate_id": "{}", "stage": "carbon", "input_values": '
        '{{"co2_efficiency": {:.4f}, "deployment_factor": {:.4f}, "production_cost": {:.4f}}}, '
        '"output_score": {:.4f}, "timestamp": "{}"}}',
        candidate.id,
        co2_efficiency,
        deployment_factor,
        production_cost,
        carbon_score,
        datetime.now(timezone.utc).isoformat(),
    )
    return carbon_score
