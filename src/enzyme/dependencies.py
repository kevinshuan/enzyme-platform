"""Enzyme feature dependencies — FastAPI DI wiring."""
from enzyme.config import enzyme_settings


def get_conserved_positions() -> list[int]:
    return enzyme_settings.conserved_positions


def get_max_mutation_threshold() -> int:
    return enzyme_settings.max_mutation_threshold
