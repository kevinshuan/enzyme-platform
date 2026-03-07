"""Enzyme feature router: POST /generate and GET /health."""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timezone
from typing import Any

import numpy as np
from fastapi import APIRouter, HTTPException
from loguru import logger

from enzyme.config import enzyme_settings
from enzyme.schemas import (
    CandidateResponse,
    FoldRequest,
    FoldResponse,
    GenerateRequest,
    GenerateResponse,
    JobStatus,
    ResponseMeta,
    ScoringWeights,
)
from enzyme.service.scoring.biological import score_biological
from enzyme.service.scoring.carbon import score_carbon
from enzyme.service.scoring.feasibility import score_feasibility
from enzyme.service.ranking import rank_candidates
from enzyme.utils import validate_sequence

from config import global_settings

if global_settings.generator_backend == "bionemo":
    from enzyme.service.bionemo_generator import generate_candidates
else:
    from enzyme.service.generator import generate_candidates

router = APIRouter()

# ---------------------------------------------------------------------------
# In-memory job store  (sufficient for single-process MVP; replace with
# Redis if horizontal scaling is needed)
# ---------------------------------------------------------------------------
_jobs: dict[str, dict[str, Any]] = {}


def _run_generate_sync(request: GenerateRequest, job_id: str) -> None:
    """Synchronous generation logic — runs inside a thread via asyncio.to_thread."""
    job = _jobs[job_id]
    try:
        job["status"] = "running"

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
        oversample = int(os.getenv("BIONEMO_OVERSAMPLE", "3"))
        is_bionemo = global_settings.generator_backend == "bionemo"
        job["total"] = request.candidates * oversample if is_bionemo else request.candidates

        def _progress(completed: int, total: int) -> None:
            job["progress"] = completed

        candidates = generate_candidates(
            base_sequence=request.base_sequence,
            mutation_rate=request.mutation_rate,
            n_candidates=request.candidates,
            conserved_positions=conserved_positions,
            rng=rng,
            max_mutation_threshold=max_mutation_threshold,
            **{"progress_callback": _progress} if is_bionemo else {},
        )

        for i, candidate in enumerate(candidates):
            bio = score_biological(candidate, conserved_positions)
            carbon = score_carbon(candidate, stability_score=bio)
            feasibility = score_feasibility(
                candidate, max_mutation_threshold=max_mutation_threshold
            )
            candidate.bio_score = bio
            candidate.carbon_score = carbon
            candidate.feasibility_score = feasibility
            job["progress"] = i + 1

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

        job["result"] = GenerateResponse(
            seed=seed,
            total_generated=len(ranked),
            weights_used=weights,
            ranked_candidates=ranked_responses,
            meta=ResponseMeta(),
        )
        job["status"] = "complete"

    except ValueError as exc:
        job["status"] = "error"
        job["error"] = str(exc)
    except Exception as exc:  # noqa: BLE001
        job["status"] = "error"
        job["error"] = f"{type(exc).__name__}: {exc}"
        logger.exception("Unexpected error in generate job {}", job_id)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/generate", response_model=JobStatus)
async def generate(request: GenerateRequest) -> JobStatus:
    """Submit a generate job. Returns job_id immediately; poll GET /jobs/{job_id}."""
    validate_sequence(request.base_sequence)

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "progress": 0,
        "total": request.candidates,
        "result": None,
        "error": None,
    }

    # Run blocking generation in a thread so the event loop stays free
    asyncio.create_task(asyncio.to_thread(_run_generate_sync, request, job_id))

    logger.info("Job {} submitted: {} candidates", job_id, request.candidates)
    return JobStatus(**_jobs[job_id])


@router.get("/jobs/{job_id}", response_model=JobStatus)
async def get_job(job_id: str) -> JobStatus:
    """Poll the status of a generate job."""
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return JobStatus(**_jobs[job_id])


@router.post("/fold", response_model=FoldResponse)
def fold(request: FoldRequest) -> FoldResponse:
    """Fold a sequence with ESMFold NIM and return PDB structure + pLDDT scores."""
    from enzyme.service.bionemo_client import get_pdb

    try:
        pdb_string, plddt = get_pdb(request.sequence)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"ESMFold NIM unavailable: {exc}",
        ) from exc

    return FoldResponse(
        sequence=request.sequence,
        pdb=pdb_string,
        plddt=plddt,
        mean_plddt=sum(plddt) / len(plddt) if plddt else 0.0,
    )


@router.get("/health")
def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok", "version": "1.0.0"}
