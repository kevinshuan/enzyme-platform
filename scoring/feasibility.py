"""Commercial feasibility scorer — sequence-based, independent of thermodynamic stability.

Manufacturability is estimated from the fraction of expression-challenging
residues in the mutated sequence (Cys and Trp), computed directly from
the amino acid sequence without reference to the biological stability score.

Biochemical rationale:
  C (Cys): free cysteines in E. coli cytoplasm form aberrant disulfide bonds
            → inclusion bodies → low soluble yield.
  W (Trp): encoded by the rarest E. coli codon (UGG, ~1.5 % usage)
            → translation bottleneck at high-yield expression.

Formula:
    challenging_fraction = (Cys_count + Trp_count) / len(sequence)
    manufacturability    = max(0, 1 − challenging_fraction / 0.20)   → [0, 1]
    difficulty           = mutation_count / max_mutation_threshold    → [0, 1]
    feasibility_score    = 0.5·(1−difficulty) + 0.5·manufacturability

All outputs are clamped to [0.0, 1.0].
manufacturability is fully independent of the biological stability (BLOSUM62) score,
eliminating the double-counting identified in the review (Major Comment 4).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.models import EnzymeCandidate

logger = logging.getLogger(__name__)

# Amino acids that create expression challenges in standard E. coli systems.
# C → disulfide scrambling / inclusion bodies; W → rare-codon bottleneck.
_EXPRESSION_CHALLENGING_AA: frozenset[str] = frozenset("CW")

# At this fraction of C+W residues, manufacturability collapses to 0.0.
# Sequences with >20 % Cys+Trp are severely production-limited.
_MAX_CHALLENGING_FRACTION: float = 0.20

# Sub-score weights — named constants
_W_DIFFICULTY = 0.5
_W_MANUFACTURABILITY = 0.5


def compute_manufacturability(sequence: str) -> float:
    """E. coli expression manufacturability proxy, normalised to [0.0, 1.0].

    Higher score = fewer expression-challenging residues = easier to produce
    at scale via recombinant expression.

    Args:
        sequence: Amino acid sequence of the mutated enzyme.

    Returns:
        manufacturability in [0.0, 1.0].  1.0 = no Cys/Trp; 0.0 = ≥20 % Cys/Trp.
    """
    challenging_fraction = (
        sum(1 for aa in sequence if aa in _EXPRESSION_CHALLENGING_AA) / len(sequence)
    )
    return max(0.0, 1.0 - challenging_fraction / _MAX_CHALLENGING_FRACTION)


def score_feasibility(
    candidate: EnzymeCandidate,
    max_mutation_threshold: int,
) -> float:
    """Compute commercial feasibility score in [0.0, 1.0].

    Higher score = easier to synthesise and manufacture at scale.

    Manufacturability is derived from the mutated sequence directly (Cys/Trp
    content) and does not depend on the biological stability score, avoiding
    the cross-scorer double-counting present in earlier versions.

    Args:
        candidate: EnzymeCandidate with mutated_sequence and mutation data.
        max_mutation_threshold: Maximum allowed mutations (from config).

    Returns:
        feasibility_score clamped to [0.0, 1.0].
    """
    difficulty = candidate.mutation_count / max(max_mutation_threshold, 1)
    difficulty = min(1.0, difficulty)  # cap at 1 for edge inputs

    manufacturability = compute_manufacturability(candidate.mutated_sequence)

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
