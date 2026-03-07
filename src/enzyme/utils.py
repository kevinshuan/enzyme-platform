"""Enzyme feature utility helpers."""
from __future__ import annotations

from fastapi import HTTPException

from enzyme.constants import VALID_AA


def validate_sequence(seq: str) -> None:
    """Raise HTTPException(422) for invalid amino acid sequences."""
    if len(seq) < 50:
        raise HTTPException(
            status_code=422,
            detail=f"base_sequence must be at least 50 characters (got {len(seq)})",
        )
    invalid = sorted({c for c in seq if c not in VALID_AA})
    if invalid:
        raise HTTPException(
            status_code=422,
            detail=f"base_sequence contains invalid characters: {invalid}",
        )
