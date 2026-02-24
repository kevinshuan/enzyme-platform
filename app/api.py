"""FastAPI router: POST /generate and GET /health."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import numpy as np
from fastapi import APIRouter, HTTPException

from app.config_loader import load_conserved_positions, load_weights_config
from app.models import (
    CandidateResponse,
    GenerateRequest,
    GenerateResponse,
    ResponseMeta,
)
from generation.mock_generator import generate_candidates
from ranking.weighted import rank_candidates
from scoring.biological import score_biological
from scoring.carbon import score_carbon
from scoring.feasibility import score_feasibility

logger = logging.getLogger(__name__)

router = APIRouter()

_VALID_AA = frozenset("ACDEFGHIKLMNPQRSTVWY")


def validate_sequence(seq: str) -> None:
    """Raise HTTPException(422) for invalid amino acid sequences.

    Checks:
      - Minimum length of 50 characters.
      - Only standard amino acid characters (Kyte-Doolittle set).
    """
    if len(seq) < 50:
        raise HTTPException(
            status_code=422,
            detail=f"base_sequence must be at least 50 characters (got {len(seq)})",
        )
    invalid = sorted({c for c in seq if c not in _VALID_AA})
    if invalid:
        raise HTTPException(
            status_code=422,
            detail=f"base_sequence contains invalid characters: {invalid}",
        )


@router.post("/generate", response_model=GenerateResponse, response_model_by_alias=True)
def generate(request: GenerateRequest) -> GenerateResponse:
    """Generate, score, and rank enzyme mutation candidates.

    Pipeline:
      1. Validate sequence (via Pydantic + validate_sequence guard)
      2. Resolve seed (user-supplied or auto-generated)
      3. Load conserved positions and weight config
      4. Generate candidates via mock generator
      5. Score each candidate: biological → carbon → feasibility
      6. Rank candidates: final_score DESC, bio_score DESC on tie
      7. Return GenerateResponse with echoed seed and _meta disclaimer
    """
    # Extra validation guard (Pydantic covers most cases; this adds HTTP context)
    validate_sequence(request.base_sequence)

    # US3: resolve seed — auto-generate if not provided
    if request.seed is not None:
        seed = request.seed
        seed_source = "user"
    else:
        seed = int(np.random.default_rng().integers(0, 2**31))
        seed_source = "auto-generated"

    # Log request metadata (US3: seed_source included per T022)
    logger.info(
        '{"event": "request", "stage": "api", "candidates": %d, '
        '"mutation_rate": %s, "seed": %d, "seed_source": "%s", "timestamp": "%s"}',
        request.candidates,
        request.mutation_rate,
        seed,
        seed_source,
        datetime.now(timezone.utc).isoformat(),
    )

    # Load runtime config
    conserved_positions = load_conserved_positions()
    default_weights, max_mutation_threshold = load_weights_config()

    # US2: use user-supplied weights when provided, else fall back to defaults
    weights = request.weights if request.weights is not None else default_weights
    weights_source = "user" if request.weights is not None else "default"

    logger.info(
        '{"event": "weights_resolved", "stage": "api", '
        '"weights_source": "%s", "timestamp": "%s"}',
        weights_source,
        datetime.now(timezone.utc).isoformat(),
    )

    # US3: single rng instance — passed through generator AND carbon scorer
    # to guarantee byte-identical output for the same seed.
    rng = np.random.default_rng(seed)

    # Generate candidates
    try:
        candidates = generate_candidates(
            base_sequence=request.base_sequence,
            mutation_rate=request.mutation_rate,
            n_candidates=request.candidates,
            conserved_positions=conserved_positions,
            rng=rng,
            max_mutation_threshold=max_mutation_threshold,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Score candidates — biological scorer first (stability_score reused by
    # carbon and feasibility scorers to avoid redundant computation)
    for candidate in candidates:
        bio = score_biological(candidate, conserved_positions)
        carbon = score_carbon(candidate, stability_score=bio, rng=rng)
        feasibility = score_feasibility(
            candidate,
            stability_score=bio,
            max_mutation_threshold=max_mutation_threshold,
        )
        candidate.bio_score = bio
        candidate.carbon_score = carbon
        candidate.feasibility_score = feasibility

    # Rank: final_score DESC, bio_score DESC on tie (FR-008)
    ranked = rank_candidates(candidates, weights)

    # Build response
    ranked_responses = [
        CandidateResponse(
            id=c.id,
            mutated_sequence=c.mutated_sequence,
            mutation_positions=c.mutation_positions,
            mutation_count=c.mutation_count,
            bio_score=c.bio_score or 0.0,
            carbon_score=c.carbon_score or 0.0,
            feasibility_score=c.feasibility_score or 0.0,
            final_score=c.final_score or 0.0,
        )
        for c in ranked
    ]

    return GenerateResponse(
        seed=seed,
        total_generated=len(ranked),
        weights_used=weights,
        ranked_candidates=ranked_responses,
        meta=ResponseMeta(),
    )


@router.get("/health")
def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok", "version": "1.0.0"}
