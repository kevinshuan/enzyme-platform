"""ESM2-based enzyme sequence generator (Phase 2).

Uses ESM2 masked language modeling to generate biologically-informed mutations.
Each position's substitution is sampled from ESM2's predicted amino acid
probability distribution rather than uniformly at random.

Set GENERATOR_BACKEND=bionemo to activate via app/api.py.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from functools import lru_cache

import numpy as np

from app.models import EnzymeCandidate

logger = logging.getLogger(__name__)

AMINO_ACIDS = list("ACDEFGHIKLMNPQRSTVWY")
_MAX_RETRIES = 100
_ESM2_MAX_SEQ_LEN = 1022  # ESM2 positional embedding limit (excl. special tokens)

MODEL_NAME = "facebook/esm2_t33_650M_UR50D"


def _get_device():
    import torch

    if torch.backends.mps.is_available():
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


@lru_cache(maxsize=1)
def _load_model():
    """Load ESM2 model and tokenizer (lazy, cached after first call)."""
    import torch
    from transformers import EsmForMaskedLM, EsmTokenizer

    logger.info('{"event": "esm2_load", "model": "%s", "timestamp": "%s"}',
                MODEL_NAME, datetime.now(timezone.utc).isoformat())

    tokenizer = EsmTokenizer.from_pretrained(MODEL_NAME)
    model = EsmForMaskedLM.from_pretrained(MODEL_NAME)
    model.eval()
    device = _get_device()
    model.to(device)

    # Build AA → token_id mapping once
    aa_token_ids = {
        aa: tokenizer.convert_tokens_to_ids(aa)
        for aa in AMINO_ACIDS
    }

    logger.info('{"event": "esm2_ready", "device": "%s", "timestamp": "%s"}',
                str(device), datetime.now(timezone.utc).isoformat())

    return tokenizer, model, device, aa_token_ids


def _softmax(x: np.ndarray) -> np.ndarray:
    e = np.exp(x - x.max())
    return e / e.sum()


def _esm2_sample_mutations(
    base_sequence: str,
    selected_positions: list[int],
    rng: np.random.Generator,
) -> dict[int, str]:
    """Run batched ESM2 inference and sample substitutions for selected positions.

    One forward pass: each item in the batch masks exactly one of the selected
    positions. Returns a mapping {position: chosen_aa}.
    """
    import torch

    tokenizer, model, device, aa_token_ids = _load_model()

    mask_token_id = tokenizer.mask_token_id
    # Tokenize the base sequence once (no masking yet)
    base_encoding = tokenizer(base_sequence, return_tensors="pt")
    input_ids_base = base_encoding["input_ids"][0]  # shape [seq_len+2] (BOS+EOS)

    # Build a batch: one row per selected position
    batch_input_ids = []
    for pos in selected_positions:
        ids = input_ids_base.clone()
        # token index: +1 for BOS token at position 0
        ids[pos + 1] = mask_token_id
        batch_input_ids.append(ids)

    batch_tensor = torch.stack(batch_input_ids).to(device)
    attention_mask = torch.ones_like(batch_tensor).to(device)

    with torch.no_grad():
        outputs = model(input_ids=batch_tensor, attention_mask=attention_mask)
    # outputs.logits shape: [batch, seq_len+2, vocab_size]

    substitutions: dict[int, str] = {}
    for batch_idx, pos in enumerate(selected_positions):
        token_pos = pos + 1  # account for BOS
        logits = outputs.logits[batch_idx, token_pos, :]  # [vocab_size]

        original_aa = base_sequence[pos]
        aa_logits = np.array([logits[aa_token_ids[aa]].item() for aa in AMINO_ACIDS])
        aa_probs = _softmax(aa_logits)

        # Exclude original AA: set its prob to 0, renormalize
        orig_idx = AMINO_ACIDS.index(original_aa)
        aa_probs[orig_idx] = 0.0
        total = aa_probs.sum()
        if total == 0.0:
            # Fallback: uniform over all other AAs (should never happen)
            aa_probs = np.ones(len(AMINO_ACIDS)) / (len(AMINO_ACIDS) - 1)
            aa_probs[orig_idx] = 0.0
        else:
            aa_probs /= total

        chosen_aa = rng.choice(AMINO_ACIDS, p=aa_probs)
        substitutions[pos] = chosen_aa

    return substitutions


def generate_candidates(
    base_sequence: str,
    mutation_rate: float,
    n_candidates: int,
    conserved_positions: list[int],
    rng: np.random.Generator,
    max_mutation_threshold: int = 20,
) -> list[EnzymeCandidate]:
    """Generate n_candidates mutated enzyme variants using ESM2 MLM.

    Drop-in replacement for mock_generator.generate_candidates.
    Preserves the rng call sequence for reproducibility:
      1. rng.random() × seq_len  (position selection)
      2. rng.choice(p=probs) × mutation_count  (AA sampling via ESM2)
      3. rng.integers() × 16  (UUID bytes)

    Args:
        base_sequence: Valid amino acid string (len ≥ 50, ≤ 1022).
        mutation_rate: Probability of mutating each position (0.0–0.2).
        n_candidates: Number of candidates to produce.
        conserved_positions: 0-indexed positions that MUST NOT be mutated.
        rng: Seeded NumPy Generator — passed in to guarantee reproducibility.
        max_mutation_threshold: Maximum mutations allowed per candidate.

    Returns:
        List of EnzymeCandidate with mutation data (scores not yet assigned).

    Raises:
        ValueError: If sequence exceeds ESM2 limit, all positions are conserved,
                    or candidates cannot be generated after retries.
    """
    if len(base_sequence) > _ESM2_MAX_SEQ_LEN:
        raise ValueError(
            f"Sequence length {len(base_sequence)} exceeds ESM2 maximum of "
            f"{_ESM2_MAX_SEQ_LEN} residues. Truncate the sequence before calling."
        )

    # Edge case: zero mutation rate → return copies of base sequence (skip ESM2)
    if mutation_rate == 0.0:
        logger.info(
            '{"event": "generate", "backend": "bionemo", "zero_rate": true, '
            '"n_candidates": %d, "timestamp": "%s"}',
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
        # Step 1: select mutation positions (same gate as mock, preserves rng call sequence)
        mutation_mask = [
            (rng.random() < mutation_rate and i not in conserved_set)
            for i in range(seq_len)
        ]
        selected_positions = [i for i, m in enumerate(mutation_mask) if m]

        # Step 2 & 3: ESM2 batched inference + rng sampling
        if selected_positions:
            substitutions = _esm2_sample_mutations(base_sequence, selected_positions, rng)
        else:
            substitutions = {}

        seq = list(base_sequence)
        mutation_positions: list[int] = []
        for pos, aa in substitutions.items():
            seq[pos] = aa
            mutation_positions.append(pos)

        mutation_count = len(mutation_positions)

        # Step 4a: Enforce at-least-one-mutation constraint
        if mutation_count == 0:
            retries = 0
            while mutation_count == 0 and retries < _MAX_RETRIES:
                pos = int(rng.choice(mutable_positions))
                original_aa = base_sequence[pos]
                # Single-position ESM2 inference for the forced mutation
                forced_subs = _esm2_sample_mutations(base_sequence, [pos], rng)
                seq[pos] = forced_subs[pos]
                mutation_positions = [pos]
                mutation_count = 1
                retries += 1
            if mutation_count == 0:
                raise ValueError(
                    "Cannot generate mutations: all positions are conserved or sequence too short"
                )

        # Step 4b: Discard candidates exceeding max threshold
        if mutation_count > max_mutation_threshold:
            continue

        # Step 5: Deterministic UUID from seeded rng (identical to mock)
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
        '{"event": "generate", "backend": "bionemo", "n_candidates": %d, '
        '"mutation_rate": %s, "timestamp": "%s"}',
        n_candidates,
        mutation_rate,
        datetime.now(timezone.utc).isoformat(),
    )
    return candidates
