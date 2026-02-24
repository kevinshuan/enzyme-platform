"""Load and validate JSON configuration files at application startup."""
from __future__ import annotations

import json
from pathlib import Path

from app.models import ScoringWeights

# Resolve config directory relative to repo root
_CONFIG_DIR = Path(__file__).parent.parent / "config"


def load_conserved_positions() -> list[int]:
    """Load conserved amino acid positions from config/conserved_regions.json.

    Returns:
        List of 0-indexed conserved position integers.

    Raises:
        RuntimeError: If the file is missing or malformed.
    """
    path = _CONFIG_DIR / "conserved_regions.json"
    if not path.exists():
        raise RuntimeError(
            f"Missing config file: {path}. "
            "Create config/conserved_regions.json with "
            '{"conserved_positions": [<int>, ...]}'
        )
    try:
        data = json.loads(path.read_text())
        positions = data["conserved_positions"]
        if not isinstance(positions, list) or not all(isinstance(p, int) for p in positions):
            raise ValueError("conserved_positions must be a list of integers")
        return positions
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Malformed config/conserved_regions.json: {exc}"
        ) from exc


def load_weights_config() -> tuple[ScoringWeights, int]:
    """Load default scoring weights and max mutation threshold from config/weights.json.

    Returns:
        Tuple of (ScoringWeights, max_mutation_threshold).

    Raises:
        RuntimeError: If the file is missing or malformed.
    """
    path = _CONFIG_DIR / "weights.json"
    if not path.exists():
        raise RuntimeError(
            f"Missing config file: {path}. "
            "Create config/weights.json with bio_weight, carbon_weight, "
            "feasibility_weight, and max_mutation_threshold."
        )
    try:
        data = json.loads(path.read_text())
        weights = ScoringWeights(
            bio_weight=data["bio_weight"],
            carbon_weight=data["carbon_weight"],
            feasibility_weight=data["feasibility_weight"],
        )
        threshold = int(data["max_mutation_threshold"])
        return weights, threshold
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Malformed config/weights.json: {exc}") from exc
