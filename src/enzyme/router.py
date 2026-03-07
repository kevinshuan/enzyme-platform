"""Enzyme feature router: POST /generate and GET /health."""
from __future__ import annotations

import os
from datetime import datetime, timezone

import numpy as np
from fastapi import APIRouter, HTTPException
from loguru import logger

from enzyme.config import enzyme_settings
from enzyme.schemas import (
    CandidateResponse,
    GenerateRequest,
    GenerateResponse,
    ResponseMeta,
    ScoringWeights,
)
from enzyme.service.scoring.biological import score_biological
from enzyme.service.scoring.carbon import score_carbon
from enzyme.service.scoring.feasibility import score_feasibility
from enzyme.service.ranking import rank_candidates
from enzyme.utils import validate_sequence

if os.getenv("GENERATOR_BACKEND", "mock") == "bionemo":
    from enzyme.service.bionemo_generator import generate_candidates  # type: ignore[import]
else:
    from enzyme.service.generator import generate_candidates

router = APIRouter()


@router.post("/generate", response_model=GenerateResponse, response_model_by_alias=True)
def generate(request: GenerateRequest) -> GenerateResponse:
    """Generate, score, and rank enzyme mutation candidates."""
    validate_sequence(request.base_sequence)

    if request.seed is not None:
        seed = request.seed
        seed_source = "user"
    else:
        seed = int(np.random.default_rng().integers(0, 2**31))
        seed_source = "auto-generated"

    logger.info(
        '{{"event": "request", "stage": "api", "candidates": {}, "mutation_rate": {}, '
        '"seed": {}, "seed_source": "{}", "timestamp": "{}"}}',
        request.candidates,
        request.mutation_rate,
        seed,
        seed_source,
        datetime.now(timezone.utc).isoformat(),
    )

    conserved_positions = enzyme_settings.conserved_positions
    max_mutation_threshold = enzyme_settings.max_mutation_threshold

    if request.weights is not None:
        weights = request.weights
        weights_source = "user"
    else:
        weights = ScoringWeights(
            bio_weight=enzyme_settings.bio_weight,
            carbon_weight=enzyme_settings.carbon_weight,
            feasibility_weight=enzyme_settings.feasibility_weight,
        )
        weights_source = "default"

    logger.info(
        '{{"event": "weights_resolved", "stage": "api", "weights_source": "{}", "timestamp": "{}"}}',
        weights_source,
        datetime.now(timezone.utc).isoformat(),
    )

    rng = np.random.default_rng(seed)

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

    for candidate in candidates:
        bio = score_biological(candidate, conserved_positions)
        carbon = score_carbon(candidate, stability_score=bio)
        feasibility = score_feasibility(candidate, max_mutation_threshold=max_mutation_threshold)
        candidate.bio_score = bio
        candidate.carbon_score = carbon
        candidate.feasibility_score = feasibility

    ranked = rank_candidates(candidates, weights)

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
