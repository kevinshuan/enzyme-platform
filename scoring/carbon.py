"""Carbon impact scorer — deterministic, sequence-based efficiency proxy.

CO₂ conversion efficiency is estimated from two sequence properties of the
mutated enzyme, both computable without a 3-D structure:

  polar_fraction    = |{aa ∈ sequence : aa ∈ POLAR_AA}| / len(sequence)
                      Polar/charged residues can H-bond with CO₂, HCO₃⁻, and
                      water; higher fraction → better substrate interaction.

  charge_neutrality = max(0, 1 − |net_charge_per_residue| / 0.5)
                      Carbonic Anhydrase operates optimally near neutral pH
                      (pI ≈ 6.9 for CA II).  Extreme net charge disrupts the
                      proton-wire network; neutrality → 1.0, extreme → 0.0.

  co2_efficiency    = 0.5·polar_fraction + 0.5·charge_neutrality  → [0, 1]

Full formula:
    co2_efficiency   = compute_co2_efficiency(mutated_sequence)
    production_cost  = min(1.0, mutation_count × 0.01)
    raw              = co2_efficiency × stability − production_cost
    carbon_score     = (raw + 1.0) / 2.0          # rescale [−1, 1] → [0, 1]

All outputs clamped to [0.0, 1.0].  Score is fully deterministic: identical
sequences always produce identical carbon scores regardless of call order.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.models import EnzymeCandidate

logger = logging.getLogger(__name__)

# Polar + charged amino acids: capable of H-bonding with CO₂ / HCO₃⁻ / water
_POLAR_AA: frozenset[str] = frozenset("STNQDEKRHY")

# His is ~9 % protonated at pH 7.4 (pKa ≈ 6.5); K and R are fully protonated
_HIS_CHARGE_PH74: float = 0.09

# Per-residue net-charge magnitude that maps to neutrality = 0.0
# (a sequence of 50 % K/R or 50 % D/E → |charge/residue| = 0.5)
_MAX_CHARGE_PER_RESIDUE: float = 0.5

# Production cost scaling — each mutation adds 1 % synthesis complexity
_PRODUCTION_COST_PER_MUTATION: float = 0.01


def compute_polar_fraction(sequence: str) -> float:
    """Fraction of polar + charged residues in *sequence*.

    Higher values indicate greater potential for CO₂ / HCO₃⁻ interaction.
    Returns a value in [0.0, 1.0].
    """
    return sum(1 for aa in sequence if aa in _POLAR_AA) / len(sequence)


def compute_charge_neutrality(sequence: str) -> float:
    """Proximity to electrical neutrality at pH 7.4, normalised to [0.0, 1.0].

    Net charge per residue:
      +1  per K or R  (fully protonated at pH 7.4)
      +0.09 per H     (pKa ≈ 6.5 → ~9 % protonated)
      −1  per D or E  (fully deprotonated at pH 7.4)

    Neutrality = max(0, 1 − |net_charge_per_residue| / 0.5)
    A sequence near zero net charge scores 1.0; extreme charge scores 0.0.
    """
    charge = (
        sum(1.0 for aa in sequence if aa in {"K", "R"})
        + sum(_HIS_CHARGE_PH74 for aa in sequence if aa == "H")
        - sum(1.0 for aa in sequence if aa in {"D", "E"})
    )
    per_residue = charge / len(sequence)
    return max(0.0, 1.0 - abs(per_residue) / _MAX_CHARGE_PER_RESIDUE)


def compute_co2_efficiency(sequence: str) -> float:
    """CO₂ conversion efficiency proxy in [0.0, 1.0], deterministic from sequence.

    Combines polar_fraction (substrate-interaction potential) and
    charge_neutrality (pH-7.4 operational fitness) with equal weight.
    """
    return (compute_polar_fraction(sequence) + compute_charge_neutrality(sequence)) / 2.0


def score_carbon(
    candidate: EnzymeCandidate,
    stability_score: float,
) -> float:
    """Compute carbon impact score in [0.0, 1.0].

    Higher score = greater estimated CO₂ reduction potential.

    Args:
        candidate: EnzymeCandidate with mutated_sequence and mutation data.
        stability_score: Pre-computed stability sub-score from biological scorer.

    Returns:
        carbon_score clamped to [0.0, 1.0].
    """
    co2_efficiency = compute_co2_efficiency(candidate.mutated_sequence)

    deployment_factor = stability_score
    production_cost = min(1.0, candidate.mutation_count * _PRODUCTION_COST_PER_MUTATION)

    raw = (co2_efficiency * deployment_factor) - production_cost
    # Rescale from potential [−1, 1] range to [0, 1]
    carbon_score = (raw + 1.0) / 2.0
    carbon_score = max(0.0, min(1.0, carbon_score))
    if not (0.0 <= carbon_score <= 1.0):
        raise RuntimeError(f"carbon_score out of range: {carbon_score}")

    logger.info(
        '{"candidate_id": "%s", "stage": "carbon", "input_values": '
        '{"co2_efficiency": %.4f, "deployment_factor": %.4f, "production_cost": %.4f}, '
        '"output_score": %.4f, "timestamp": "%s"}',
        candidate.id,
        co2_efficiency,
        deployment_factor,
        production_cost,
        carbon_score,
        datetime.now(timezone.utc).isoformat(),
    )
    return carbon_score
