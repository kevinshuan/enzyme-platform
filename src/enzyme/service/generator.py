"""Mock enzyme sequence generator (MVP).

Generates amino acid mutation candidates using NumPy's PCG64 RNG.
Replace this module's logic with BioNeMo inference for Phase 2.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import numpy as np
from loguru import logger

from enzyme.constants import AMINO_ACIDS
from enzyme.models import EnzymeCandidate

_MAX_RETRIES = 100  # retries before giving up on a single candidate


def generate_candidates(
    base_sequence: str,
    mutation_rate: float,
    n_candidates: int,
    conserved_positions: list[int],
    rng: np.random.Generator,
    max_mutation_threshold: int = 20,
) -> list[EnzymeCandidate]:
    """Generate n_candidates mutated enzyme variants.

    Args:
        base_sequence: Valid amino acid string (len ≥ 50).
        mutation_rate: Probability of mutating each position (0.0–0.2).
        n_candidates: Number of candidates to produce.
        conserved_positions: 0-indexed positions that MUST NOT be mutated.
        rng: Seeded NumPy Generator — passed in to guarantee reproducibility.
        max_mutation_threshold: Maximum mutations allowed per candidate.

    Returns:
        List of EnzymeCandidate with mutation data (scores not yet assigned).

    Raises:
        ValueError: If all mutable positions are exhausted after retries.
    """
    # Edge case: zero mutation rate → return copies of base sequence
    if mutation_rate == 0.0:
        logger.info(
            '{{"event": "generate", "zero_rate": true, "n_candidates": {}, "timestamp": "{}"}}',
            n_candidates,
            datetime.now(timezone.utc).isoformat(),
        )

        def _det_id() -> str:
            id_bytes = rng.integers(0, 256, size=16, dtype=np.uint8)
            return str(uuid.UUID(bytes=bytes(id_bytes.tolist())))

        return [
            EnzymeCandidate(
                id=_det_id(),
                base_sequence=base_sequence,
                mutated_sequence=base_sequence,
                mutation_positions=[],
                mutation_count=0,
            )
            for _ in range(n_candidates)
        ]

    conserved_set = set(conserved_positions)
    seq_len = len(base_sequence)
    mutable_positions = [i for i in range(seq_len) if i not in conserved_set]

    if not mutable_positions:
        raise ValueError(
            "Cannot generate mutations: all positions are conserved or sequence too short"
        )

    candidates: list[EnzymeCandidate] = []
    while len(candidates) < n_candidates:
        seq = list(base_sequence)
        mutation_positions: list[int] = []

        for pos in range(seq_len):
            if pos in conserved_set:
                continue
            if rng.random() < mutation_rate:
                original_aa = seq[pos]
                alternatives = [aa for aa in AMINO_ACIDS if aa != original_aa]
                seq[pos] = rng.choice(alternatives)  # type: ignore[arg-type]
                mutation_positions.append(pos)

        mutation_count = len(mutation_positions)

        # Discard candidates with no mutations — regenerate
        if mutation_count == 0:
            retries = 0
            while mutation_count == 0 and retries < _MAX_RETRIES:
                pos = int(rng.choice(mutable_positions))
                original_aa = seq[pos]
                alternatives = [aa for aa in AMINO_ACIDS if aa != original_aa]
                seq[pos] = rng.choice(alternatives)  # type: ignore[arg-type]
                mutation_positions = [pos]
                mutation_count = 1
                retries += 1
            if mutation_count == 0:
                raise ValueError(
                    "Cannot generate mutations: all positions are conserved or sequence too short"
                )

        # Discard candidates exceeding max threshold
        if mutation_count > max_mutation_threshold:
            continue

        # Generate a deterministic UUID from the seeded rng
        id_bytes = rng.integers(0, 256, size=16, dtype=np.uint8)
        candidate_id = str(uuid.UUID(bytes=bytes(id_bytes.tolist())))

        candidates.append(
            EnzymeCandidate(
                id=candidate_id,
                base_sequence=base_sequence,
                mutated_sequence="".join(seq),
                mutation_positions=sorted(mutation_positions),
                mutation_count=mutation_count,
            )
        )

    logger.info(
        '{{"event": "generate", "n_candidates": {}, "mutation_rate": {}, "timestamp": "{}"}}',
        n_candidates,
        mutation_rate,
        datetime.now(timezone.utc).isoformat(),
    )
    return candidates
