"""Biological viability scorer using BLOSUM62 substitution matrix.

Formula:
    stability      = mean(normalize(BLOSUM62[base_aa][mut_aa]) for each mutation)
                   = mean((BLOSUM62_score + 4) / 7)   -- [0, 1], 1.0 if no mutations
    mutation_pen   = mutation_count / len(sequence)
    conserved_pen  = mutations_in_conserved / mutation_count
    bio_score      = 0.4·stability + 0.4·(1−mutation_pen) + 0.2·(1−conserved_pen)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.models import EnzymeCandidate

logger = logging.getLogger(__name__)

# BLOSUM62 substitution matrix — Henikoff & Henikoff (1992)
# Covers all 20 standard amino acids: ACDEFGHIKLMNPQRSTVWY
BLOSUM62: dict[str, dict[str, int]] = {
    "A": {"A":  4, "C":  0, "D": -2, "E": -1, "F": -2, "G":  0, "H": -2, "I": -1, "K": -1, "L": -1, "M": -1, "N": -2, "P": -1, "Q": -1, "R": -1, "S":  1, "T":  0, "V":  0, "W": -3, "Y": -2},
    "C": {"A":  0, "C":  9, "D": -3, "E": -4, "F": -2, "G": -3, "H": -3, "I": -1, "K": -3, "L": -1, "M": -1, "N": -3, "P": -3, "Q": -3, "R": -3, "S": -1, "T": -1, "V": -1, "W": -2, "Y": -2},
    "D": {"A": -2, "C": -3, "D":  6, "E":  2, "F": -3, "G": -1, "H": -1, "I": -3, "K": -1, "L": -4, "M": -3, "N":  1, "P": -1, "Q":  0, "R": -2, "S":  0, "T": -1, "V": -3, "W": -4, "Y": -3},
    "E": {"A": -1, "C": -4, "D":  2, "E":  5, "F": -3, "G": -2, "H":  0, "I": -3, "K":  1, "L": -3, "M": -2, "N":  0, "P": -1, "Q":  2, "R":  0, "S":  0, "T": -1, "V": -2, "W": -3, "Y": -2},
    "F": {"A": -2, "C": -2, "D": -3, "E": -3, "F":  6, "G": -3, "H": -1, "I":  0, "K": -3, "L":  0, "M":  0, "N": -3, "P": -4, "Q": -3, "R": -3, "S": -2, "T": -2, "V": -1, "W":  1, "Y":  3},
    "G": {"A":  0, "C": -3, "D": -1, "E": -2, "F": -3, "G":  6, "H": -2, "I": -4, "K": -2, "L": -4, "M": -3, "N":  0, "P": -2, "Q": -2, "R": -2, "S":  0, "T": -2, "V": -3, "W": -2, "Y": -3},
    "H": {"A": -2, "C": -3, "D": -1, "E":  0, "F": -1, "G": -2, "H":  8, "I": -3, "K": -1, "L": -3, "M": -2, "N":  1, "P": -2, "Q":  0, "R":  0, "S": -1, "T": -2, "V": -3, "W": -2, "Y":  2},
    "I": {"A": -1, "C": -1, "D": -3, "E": -3, "F":  0, "G": -4, "H": -3, "I":  4, "K": -1, "L":  2, "M":  1, "N": -3, "P": -3, "Q": -3, "R": -3, "S": -2, "T": -1, "V":  3, "W": -3, "Y": -1},
    "K": {"A": -1, "C": -3, "D": -1, "E":  1, "F": -3, "G": -2, "H": -1, "I": -1, "K":  5, "L": -2, "M": -1, "N":  0, "P": -1, "Q":  1, "R":  2, "S":  0, "T": -1, "V": -2, "W": -3, "Y": -2},
    "L": {"A": -1, "C": -1, "D": -4, "E": -3, "F":  0, "G": -4, "H": -3, "I":  2, "K": -2, "L":  4, "M":  2, "N": -3, "P": -3, "Q": -2, "R": -2, "S": -2, "T": -1, "V":  1, "W": -2, "Y": -1},
    "M": {"A": -1, "C": -1, "D": -3, "E": -2, "F":  0, "G": -3, "H": -2, "I":  1, "K": -1, "L":  2, "M":  5, "N": -2, "P": -2, "Q":  0, "R": -1, "S": -1, "T": -1, "V":  1, "W": -1, "Y": -1},
    "N": {"A": -2, "C": -3, "D":  1, "E":  0, "F": -3, "G":  0, "H":  1, "I": -3, "K":  0, "L": -3, "M": -2, "N":  6, "P": -2, "Q":  0, "R":  0, "S":  1, "T":  0, "V": -3, "W": -4, "Y": -2},
    "P": {"A": -1, "C": -3, "D": -1, "E": -1, "F": -4, "G": -2, "H": -2, "I": -3, "K": -1, "L": -3, "M": -2, "N": -2, "P":  7, "Q": -1, "R": -2, "S": -1, "T": -1, "V": -2, "W": -4, "Y": -3},
    "Q": {"A": -1, "C": -3, "D":  0, "E":  2, "F": -3, "G": -2, "H":  0, "I": -3, "K":  1, "L": -2, "M":  0, "N":  0, "P": -1, "Q":  5, "R":  1, "S":  0, "T": -1, "V": -2, "W": -2, "Y": -1},
    "R": {"A": -1, "C": -3, "D": -2, "E":  0, "F": -3, "G": -2, "H":  0, "I": -3, "K":  2, "L": -2, "M": -1, "N":  0, "P": -2, "Q":  1, "R":  5, "S": -1, "T": -1, "V": -3, "W": -3, "Y": -2},
    "S": {"A":  1, "C": -1, "D":  0, "E":  0, "F": -2, "G":  0, "H": -1, "I": -2, "K":  0, "L": -2, "M": -1, "N":  1, "P": -1, "Q":  0, "R": -1, "S":  4, "T":  1, "V": -2, "W": -3, "Y": -2},
    "T": {"A":  0, "C": -1, "D": -1, "E": -1, "F": -2, "G": -2, "H": -2, "I": -1, "K": -1, "L": -1, "M": -1, "N":  0, "P": -1, "Q": -1, "R": -1, "S":  1, "T":  5, "V":  0, "W": -2, "Y": -2},
    "V": {"A":  0, "C": -1, "D": -3, "E": -2, "F": -1, "G": -3, "H": -3, "I":  3, "K": -2, "L":  1, "M":  1, "N": -3, "P": -2, "Q": -2, "R": -3, "S": -2, "T":  0, "V":  4, "W": -3, "Y": -1},
    "W": {"A": -3, "C": -2, "D": -4, "E": -3, "F":  1, "G": -2, "H": -2, "I": -3, "K": -3, "L": -2, "M": -1, "N": -4, "P": -4, "Q": -2, "R": -3, "S": -3, "T": -2, "V": -3, "W": 11, "Y":  2},
    "Y": {"A": -2, "C": -2, "D": -3, "E": -2, "F":  3, "G": -3, "H":  2, "I": -1, "K": -2, "L": -1, "M": -1, "N": -2, "P": -3, "Q": -1, "R": -2, "S": -2, "T": -2, "V": -1, "W":  2, "Y":  7},
}

# Normalization constants for off-diagonal substitution scores
# Off-diagonal range: min = -4 (e.g. W→R), max = 3 (e.g. I→V)
_BLOSUM62_SUB_MIN: int = -4
_BLOSUM62_SUB_MAX: int = 3
_BLOSUM62_SUB_RANGE: int = _BLOSUM62_SUB_MAX - _BLOSUM62_SUB_MIN  # 7

# Sub-score weights — named constants, no magic numbers
_W_STABILITY = 0.4
_W_MUTATION = 0.4
_W_CONSERVED = 0.2


def compute_blosum62_stability(
    base_sequence: str,
    mutated_sequence: str,
    mutation_positions: list[int],
) -> float:
    """Per-mutation BLOSUM62 conservation score, normalized to [0, 1].

    For each mutated position: normalized_score = (BLOSUM62[orig][new] + 4) / 7
    Final stability = mean of per-mutation scores.
    If no mutations: returns 1.0 (sequence unchanged = maximally stable).
    """
    if not mutation_positions:
        return 1.0
    scores = [
        (BLOSUM62[base_sequence[pos]][mutated_sequence[pos]] - _BLOSUM62_SUB_MIN)
        / _BLOSUM62_SUB_RANGE
        for pos in mutation_positions
    ]
    return sum(scores) / len(scores)


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
    stability = compute_blosum62_stability(
        candidate.base_sequence,
        candidate.mutated_sequence,
        candidate.mutation_positions,
    )

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
