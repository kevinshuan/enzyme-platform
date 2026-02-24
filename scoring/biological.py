"""Biological viability scorer using Kyte-Doolittle hydrophobicity index.

Formula (corrected — divides by scale range 9.0 to guarantee [0,1]):
    stability      = 1.0 - abs(mean_hydro(base) - mean_hydro(mutated)) / HYDRO_SCALE
    mutation_penalty  = mutation_count / len(base_sequence)
    conserved_penalty = mutations_in_conserved / mutation_count
    bio_score = 0.4*stability + 0.4*(1-mutation_penalty) + 0.2*(1-conserved_penalty)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.models import EnzymeCandidate

logger = logging.getLogger(__name__)

# Kyte & Doolittle (1982) hydrophobicity index for all 20 standard amino acids
KYTE_DOOLITTLE: dict[str, float] = {
    "A": 1.8,  "C": 2.5,  "D": -3.5, "E": -3.5, "F": 2.8,
    "G": -0.4, "H": -3.2, "I": 4.5,  "K": -3.9, "L": 3.8,
    "M": 1.9,  "N": -3.5, "P": -1.6, "Q": -3.5, "R": -4.5,
    "S": -0.8, "T": -0.7, "V": 4.2,  "W": -0.9, "Y": -1.3,
}

# Scale range: max(4.5) - min(-4.5) = 9.0
HYDRO_SCALE: float = 9.0

# Sub-score weights — named constants, no magic numbers
_W_STABILITY = 0.4
_W_MUTATION = 0.4
_W_CONSERVED = 0.2


def compute_hydrophobicity(sequence: str) -> float:
    """Mean Kyte-Doolittle hydrophobicity for an amino acid sequence."""
    return sum(KYTE_DOOLITTLE[aa] for aa in sequence) / len(sequence)


def score_biological(
    candidate: EnzymeCandidate,
    conserved_positions: list[int],
) -> float:
    """Compute biological viability score in [0.0, 1.0].

    Higher score = more biologically plausible mutation.

    Args:
        candidate: EnzymeCandidate with base_sequence and mutated_sequence.
        conserved_positions: 0-indexed positions that must not be mutated.

    Returns:
        bio_score clamped to [0.0, 1.0].
    """
    hydro_orig = compute_hydrophobicity(candidate.base_sequence)
    hydro_mut = compute_hydrophobicity(candidate.mutated_sequence)

    # Stability: normalised hydrophobicity change (÷ 9.0 to guarantee [0,1])
    stability = 1.0 - abs(hydro_orig - hydro_mut) / HYDRO_SCALE
    stability = max(0.0, min(1.0, stability))

    # Mutation penalty: fraction of positions mutated
    mutation_penalty = candidate.mutation_count / len(candidate.base_sequence)

    # Conserved penalty: fraction of mutations landing in conserved positions
    if candidate.mutation_count == 0:
        conserved_penalty = 0.0
    else:
        conserved_set = set(conserved_positions)
        mutations_in_conserved = sum(
            1 for p in candidate.mutation_positions if p in conserved_set
        )
        conserved_penalty = mutations_in_conserved / candidate.mutation_count

    bio_score = (
        _W_STABILITY * stability
        + _W_MUTATION * (1.0 - mutation_penalty)
        + _W_CONSERVED * (1.0 - conserved_penalty)
    )
    bio_score = max(0.0, min(1.0, bio_score))
    if not (0.0 <= bio_score <= 1.0):
        raise RuntimeError(f"bio_score out of range: {bio_score}")

    logger.info(
        '{"candidate_id": "%s", "stage": "biological", "input_values": '
        '{"stability": %.4f, "mutation_penalty": %.4f, "conserved_penalty": %.4f}, '
        '"output_score": %.4f, "timestamp": "%s"}',
        candidate.id,
        stability,
        mutation_penalty,
        conserved_penalty,
        bio_score,
        datetime.now(timezone.utc).isoformat(),
    )
    return bio_score
