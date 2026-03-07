"""Enzyme feature configuration — loads at import time.

Conserved positions source (priority order):
  1. ALPHAFOLD_UNIPROT_ID env var set → fetch from AlphaFold DB API
  2. Fallback → config/conserved_regions.json

Weights and mutation threshold always come from config/weights.json.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from loguru import logger

_CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


def _load_conserved_positions_from_json() -> list[int]:
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


def _load_conserved_positions() -> list[int]:
    """Load conserved positions from AlphaFold DB if configured, else from JSON."""
    uniprot_id = os.getenv("ALPHAFOLD_UNIPROT_ID", "").strip()
    if not uniprot_id:
        logger.info("ALPHAFOLD_UNIPROT_ID not set — loading conserved positions from JSON.")
        return _load_conserved_positions_from_json()

    threshold = float(os.getenv("ALPHAFOLD_PLDDT_THRESHOLD", "90.0"))
    logger.info(
        "ALPHAFOLD_UNIPROT_ID={} — fetching conserved positions from AlphaFold DB (threshold={:.0f}).",
        uniprot_id,
        threshold,
    )
    try:
        from enzyme.service.alphafold_client import fetch_conserved_positions
        return fetch_conserved_positions(uniprot_id, threshold=threshold)
    except Exception as exc:
        logger.warning(
            "AlphaFold DB fetch failed ({}): {} — falling back to conserved_regions.json.",
            type(exc).__name__,
            exc,
        )
        return _load_conserved_positions_from_json()


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
