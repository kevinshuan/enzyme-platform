"""Enzyme feature configuration — loads JSON config files at import time."""
from __future__ import annotations

import json
from pathlib import Path

# Config directory is at repo root (sibling of src/)
_CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


def _load_conserved_positions() -> list[int]:
    path = _CONFIG_DIR / "conserved_regions.json"
    if not path.exists():
        raise RuntimeError(
            f"Missing config file: {path}. "
            'Create config/conserved_regions.json with {"conserved_positions": [<int>, ...]}'
        )
    try:
        data = json.loads(path.read_text())
        positions = data["conserved_positions"]
        if not isinstance(positions, list) or not all(isinstance(p, int) for p in positions):
            raise ValueError("conserved_positions must be a list of integers")
        return positions
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Malformed config/conserved_regions.json: {exc}") from exc


def _load_weights_config() -> tuple[float, float, float, int]:
    path = _CONFIG_DIR / "weights.json"
    if not path.exists():
        raise RuntimeError(
            f"Missing config file: {path}. "
            "Create config/weights.json with bio_weight, carbon_weight, "
            "feasibility_weight, and max_mutation_threshold."
        )
    try:
        data = json.loads(path.read_text())
        return (
            float(data["bio_weight"]),
            float(data["carbon_weight"]),
            float(data["feasibility_weight"]),
            int(data["max_mutation_threshold"]),
        )
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Malformed config/weights.json: {exc}") from exc


class _EnzymeSettings:
    """Loaded-once enzyme feature configuration."""

    def __init__(self) -> None:
        self.conserved_positions: list[int] = _load_conserved_positions()
        bio, carbon, feasibility, threshold = _load_weights_config()
        self.bio_weight: float = bio
        self.carbon_weight: float = carbon
        self.feasibility_weight: float = feasibility
        self.max_mutation_threshold: int = threshold


enzyme_settings = _EnzymeSettings()
