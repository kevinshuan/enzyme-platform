"""Internal domain models for the enzyme feature."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict


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
