"""Pydantic v2 request/response models for the enzyme platform API."""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict


class ScoringWeights(BaseModel):
    """Scoring weights for the three candidate dimensions. Must sum to 1.0 ±0.001."""

    bio_weight: float = Field(default=0.3, ge=0.0, description="Weight for biological score")
    carbon_weight: float = Field(default=0.4, ge=0.0, description="Weight for carbon impact score")
    feasibility_weight: float = Field(default=0.3, ge=0.0, description="Weight for feasibility score")

    @model_validator(mode="after")
    def weights_must_sum_to_one(self) -> "ScoringWeights":
        total = self.bio_weight + self.carbon_weight + self.feasibility_weight
        if abs(total - 1.0) > 0.001:
            raise ValueError(
                f"weights must sum to 1.0 (got {total:.4f}, tolerance ±0.001)"
            )
        return self


class EnzymeCandidate(BaseModel):
    """Internal representation of a mutated enzyme candidate with scores."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str
    base_sequence: str
    mutated_sequence: str
    mutation_positions: list[int]
    mutation_count: int

    bio_score: Optional[float] = None
    carbon_score: Optional[float] = None
    feasibility_score: Optional[float] = None
    final_score: Optional[float] = None


class GenerateRequest(BaseModel):
    """Request body for POST /generate."""

    base_sequence: str = Field(..., description="Base amino acid sequence (min 50 chars)")
    mutation_rate: float = Field(
        ..., ge=0.0, le=0.2, description="Probability of mutation per position (0.001–0.2)"
    )
    candidates: int = Field(
        ..., ge=1, le=1000, description="Number of candidates to generate (1–1000)"
    )
    weights: Optional[ScoringWeights] = Field(
        default=None, description="Scoring weights; defaults applied if omitted"
    )
    seed: Optional[int] = Field(
        default=None, ge=0, description="Random seed for reproducibility"
    )

    @field_validator("base_sequence")
    @classmethod
    def sequence_must_be_valid(cls, v: str) -> str:
        if len(v) < 50:
            raise ValueError(
                f"base_sequence must be at least 50 characters (got {len(v)})"
            )
        valid = set("ACDEFGHIKLMNPQRSTVWY")
        invalid = sorted({c for c in v if c not in valid})
        if invalid:
            raise ValueError(f"base_sequence contains invalid characters: {invalid}")
        return v


class CandidateResponse(BaseModel):
    """Serialised candidate returned in API responses."""

    id: str
    mutated_sequence: str
    mutation_positions: list[int]
    mutation_count: int
    bio_score: float
    carbon_score: float
    feasibility_score: float
    final_score: float


class ResponseMeta(BaseModel):
    """Metadata attached to every GenerateResponse."""

    disclaimer: str = (
        "All scores are simulation proxies. Not wet-lab validated predictions."
    )
    sort_order: str = "final_score DESC, bio_score DESC on tie"


class GenerateResponse(BaseModel):
    """Response body for POST /generate."""

    seed: int
    total_generated: int
    weights_used: ScoringWeights
    ranked_candidates: list[CandidateResponse]
    meta: ResponseMeta = Field(default_factory=ResponseMeta, alias="_meta")

    model_config = ConfigDict(populate_by_name=True)
