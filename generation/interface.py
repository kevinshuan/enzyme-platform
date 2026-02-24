"""GeneratorInterface Protocol — defines the contract for sequence mutation generators.

Any implementation (mock or real) must conform to this interface.
Swapping the mock generator for BioNeMo requires only replacing the implementation;
the scoring, ranking, and API layers remain unchanged.
"""
from __future__ import annotations

from typing import Protocol

import numpy as np

from app.models import EnzymeCandidate


class GeneratorInterface(Protocol):
    """Protocol defining the contract for enzyme sequence generators.

    Implementations:
      - generation/mock_generator.py  (MVP — random mutation)
      - BioNeMo inference adapter     (Phase 2)
    """

    def generate(
        self,
        base_sequence: str,
        mutation_rate: float,
        n_candidates: int,
        conserved_positions: list[int],
        rng: np.random.Generator,
    ) -> list[EnzymeCandidate]:
        # BioNeMo: replace with real inference
        ...
