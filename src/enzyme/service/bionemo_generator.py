"""BioNeMo Phase 2 generator — ESMFold structural validation.

Drop-in replacement for ``enzyme.service.generator`` when
``GLOBAL_GENERATOR_BACKEND=bionemo``.  The public ``generate_candidates``
function has an identical signature so the router requires zero changes.

How it works
------------
  1. Generate ``n_candidates × OVERSAMPLE_FACTOR`` candidates via random
     mutation (identical to the mock generator).
  2. POST each candidate sequence to NVIDIA NIM ESMFold.
  3. Parse per-residue pLDDT from the returned PDB structure.
  4. Rank candidates by mean pLDDT — higher pLDDT = mutations better
     preserve the protein's 3D fold.
  5. Return top ``n_candidates`` structurally viable candidates.

Why this is better than random alone
-------------------------------------
Random mutations can disrupt secondary structure, hydrogen-bonding networks,
or hydrophobic cores.  ESMFold filters these out *before* downstream scoring,
so only structurally sound variants reach the ranking stage.

Fallback
--------
If ESMFold NIM is unavailable, the generator logs a warning and returns the
randomly generated candidates (sorted by mutation count as a heuristic proxy
for structural impact — fewer mutations = less disruption).

Environment variables
---------------------
  BIONEMO_API_KEY         — NVIDIA NIM API key
  BIONEMO_API_BASE        — NIM base URL (default: https://health.api.nvidia.com/v1)
  BIONEMO_OVERSAMPLE      — How many candidates to generate before filtering
                            (default: 3 × n_candidates)
"""
from __future__ import annotations

import os
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import numpy as np
from loguru import logger

from enzyme.constants import AMINO_ACIDS
from enzyme.models import EnzymeCandidate
from enzyme.service.bionemo_client import fold_sequence

_MAX_RETRIES = 100
_DEFAULT_OVERSAMPLE = 3
_DEFAULT_MAX_WORKERS = 8  # concurrent ESMFold calls


def generate_candidates(
    base_sequence: str,
    mutation_rate: float,
    n_candidates: int,
    conserved_positions: list[int],
    rng: np.random.Generator,
    max_mutation_threshold: int = 20,
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[EnzymeCandidate]:
    """Generate *n_candidates* structurally validated enzyme variants.

    Generates OVERSAMPLE × n_candidates candidates via random mutation,
    scores each with ESMFold (NVIDIA NIM), and returns the top n_candidates
    by mean pLDDT.  Falls back to random-only on API failure.

    Args:
        base_sequence: Valid amino acid string (len ≥ 50).
        mutation_rate: Probability of mutating each mutable position (0.0–0.2).
        n_candidates: Number of candidates to return.
        conserved_positions: 0-indexed positions that MUST NOT be mutated.
        rng: Seeded NumPy Generator — passed in to guarantee reproducibility.
        max_mutation_threshold: Maximum mutations allowed per candidate.

    Returns:
        List of EnzymeCandidate (scores not yet assigned).

    Raises:
        ValueError: If all positions are conserved.
    """
    conserved_set = set(conserved_positions)
    seq_len = len(base_sequence)
    mutable_positions = [i for i in range(seq_len) if i not in conserved_set]

    if not mutable_positions:
        raise ValueError(
            "Cannot generate mutations: all positions are conserved or sequence too short"
        )

    if mutation_rate == 0.0:
        return _zero_rate_candidates(base_sequence, n_candidates, rng)

    oversample = int(os.getenv("BIONEMO_OVERSAMPLE", str(_DEFAULT_OVERSAMPLE)))
    n_generate = n_candidates * oversample

    logger.info(
        "BioNeMo generator: generating {} candidates ({}× oversample), ESMFold filtering → top {}",
        n_generate,
        oversample,
        n_candidates,
    )

    # Step 1: generate n_generate random candidates
    pool = _generate_pool(
        base_sequence=base_sequence,
        mutable_positions=mutable_positions,
        conserved_set=conserved_set,
        mutation_rate=mutation_rate,
        max_mutation_threshold=max_mutation_threshold,
        n=n_generate,
        rng=rng,
    )

    # Step 2: score each with ESMFold (parallel)
    max_workers = int(os.getenv("BIONEMO_MAX_WORKERS", str(_DEFAULT_MAX_WORKERS)))
    scored = _score_with_esmfold_parallel(pool, max_workers=max_workers, progress_callback=progress_callback)

    if scored:
        # Sort by mean pLDDT descending → structurally best candidates first
        scored.sort(key=lambda x: x[1], reverse=True)
        logger.info(
            "ESMFold scoring complete: top pLDDT={:.1f} bottom pLDDT={:.1f}",
            scored[0][1],
            scored[-1][1],
        )
        result = [c for c, _ in scored[:n_candidates]]
    else:
        # Full fallback: return pool sorted by mutation count (fewer = safer)
        logger.warning(
            "ESMFold unavailable — returning top {} by mutation count", n_candidates
        )
        pool.sort(key=lambda c: c.mutation_count)
        result = pool[:n_candidates]

    logger.info(
        '{{"event": "generate_bionemo", "n_candidates": {}, "pool_size": {}, '
        '"esmfold_scored": {}, "timestamp": "{}"}}',
        len(result),
        len(pool),
        len(scored),
        datetime.now(timezone.utc).isoformat(),
    )
    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _generate_pool(
    base_sequence: str,
    mutable_positions: list[int],
    conserved_set: set[int],
    mutation_rate: float,
    max_mutation_threshold: int,
    n: int,
    rng: np.random.Generator,
) -> list[EnzymeCandidate]:
    """Generate n random mutation candidates (same logic as mock generator)."""
    candidates: list[EnzymeCandidate] = []
    attempts = 0
    max_attempts = n * _MAX_RETRIES

    while len(candidates) < n and attempts < max_attempts:
        attempts += 1
        seq = list(base_sequence)
        mutation_positions: list[int] = []

        for pos in mutable_positions:
            if rng.random() < mutation_rate:
                alts = [aa for aa in AMINO_ACIDS if aa != base_sequence[pos]]
                seq[pos] = str(rng.choice(alts))  # type: ignore[arg-type]
                mutation_positions.append(pos)

        if not mutation_positions:
            pos = int(rng.choice(mutable_positions))
            alts = [aa for aa in AMINO_ACIDS if aa != base_sequence[pos]]
            seq[pos] = str(rng.choice(alts))  # type: ignore[arg-type]
            mutation_positions = [pos]

        if len(mutation_positions) > max_mutation_threshold:
            continue

        id_bytes = rng.integers(0, 256, size=16, dtype=np.uint8)
        candidates.append(
            EnzymeCandidate(
                id=str(uuid.UUID(bytes=bytes(id_bytes.tolist()))),
                base_sequence=base_sequence,
                mutated_sequence="".join(seq),
                mutation_positions=sorted(mutation_positions),
                mutation_count=len(mutation_positions),
            )
        )

    return candidates


def _score_with_esmfold_parallel(
    candidates: list[EnzymeCandidate],
    max_workers: int = _DEFAULT_MAX_WORKERS,
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[tuple[EnzymeCandidate, float]]:
    """Call ESMFold NIM for all candidates in parallel threads.

    Args:
        candidates: Pool of candidates to fold.
        max_workers: Max concurrent ESMFold HTTP calls.
        progress_callback: Called with (completed, total) after each fold completes.

    Returns:
        List of (candidate, mean_pLDDT) sorted by submission order.
        Returns empty list on first API failure (triggers fallback).
    """
    total = len(candidates)
    results: dict[int, tuple[EnzymeCandidate, float]] = {}
    completed = 0

    def _fold_one(idx: int, candidate: EnzymeCandidate):
        plddt = fold_sequence(candidate.mutated_sequence)
        mean = sum(plddt) / len(plddt) if plddt else 0.0
        return idx, candidate, mean

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_fold_one, i, c): i
            for i, c in enumerate(candidates)
        }
        for future in as_completed(futures):
            try:
                idx, candidate, mean = future.result()
                results[idx] = (candidate, mean)
                completed += 1
                logger.debug(
                    "ESMFold [{}/{}] id={:.8} mean_pLDDT={:.1f} mutations={}",
                    completed, total, candidate.id, mean, candidate.mutation_count,
                )
                if progress_callback:
                    progress_callback(completed, total)
            except Exception as exc:  # noqa: BLE001
                logger.warning("ESMFold NIM error — falling back to unscored pool: {}", exc)
                executor.shutdown(wait=False, cancel_futures=True)
                return []

    # Return in original order
    return [results[i] for i in sorted(results)]


def _zero_rate_candidates(
    base_sequence: str,
    n_candidates: int,
    rng: np.random.Generator,
) -> list[EnzymeCandidate]:
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
