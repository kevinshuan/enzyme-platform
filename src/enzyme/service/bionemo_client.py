"""NVIDIA NIM BioNeMo client — ESMFold structure prediction.

Phase 2 uses *ESMFold* via NVIDIA NIM to structurally validate mutated enzyme
candidates.  Each candidate sequence is folded in silico; the mean per-residue
pLDDT confidence score measures how well the mutation preserves the protein's
3D structure.

Integration model
-----------------
  1. Generate candidates via random mutation (mock generator).
  2. POST each candidate sequence to ESMFold NIM.
  3. Parse per-residue pLDDT scores from the returned PDB string.
  4. Rank candidates by mean pLDDT — higher = better structure preservation.
  5. Return top-N candidates for downstream scoring.

This is more biologically meaningful than random generation alone because
mutations that destabilise the fold are filtered out before scoring.

NIM endpoint (ESMFold)
----------------------
  POST {BIONEMO_API_BASE}/biology/nvidia/esmfold
  Authorization: Bearer {BIONEMO_API_KEY}
  Content-Type: application/json

  Request  : {"sequence": "MKTAYAKQR..."}
  Response : {"pdbs": ["<PDB file content as string>", ...]}

  pLDDT is stored in the B-factor column of ATOM records in the PDB output.

Cloud NIM (NVIDIA API Catalog)
  BIONEMO_API_KEY=nvapi-...
  BIONEMO_API_BASE=https://health.api.nvidia.com/v1   (default)

Self-hosted NIM
  docker run --gpus all -p 8080:8080 \\
    nvcr.io/nvidia/nim/esmfold:latest
  BIONEMO_API_BASE=http://localhost:8080/v1
"""
from __future__ import annotations

import os
import re

import requests
from loguru import logger

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DEFAULT_API_BASE = "https://health.api.nvidia.com/v1"
_ESMFOLD_PATH = "biology/nvidia/esmfold"
_REQUEST_TIMEOUT = 60  # ESMFold can take ~10–30 s for long sequences

# PDB B-factor column: cols 61–66 contain per-residue pLDDT
# ATOM      1  CA  MET A   1      -8.13  -6.01 -14.13  1.00 60.92           C
_PLDDT_RE = re.compile(
    r"^ATOM\s+\d+\s+CA\s+\w+\s+\w\s+\d+\s+"  # up to residue
    r"[\s\d.-]+\s+[\s\d.-]+\s+[\s\d.-]+\s+"   # x y z
    r"[\d.]+\s+([\d.]+)",                       # occupancy  pLDDT(B-factor)
    re.MULTILINE,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def fold_sequence(
    sequence: str,
    *,
    api_key: str | None = None,
    api_base: str | None = None,
    timeout: int = _REQUEST_TIMEOUT,
) -> list[float]:
    """Fold a protein sequence with ESMFold NIM; return per-residue pLDDT scores.

    Args:
        sequence: Amino acid sequence (standard 20 AAs, no gaps or masks).
        api_key: NVIDIA NIM API key.  Defaults to ``BIONEMO_API_KEY`` env var.
        api_base: NIM base URL.  Defaults to ``BIONEMO_API_BASE`` env var or
                  ``https://health.api.nvidia.com/v1``.
        timeout: HTTP request timeout in seconds (ESMFold ~10–30 s).

    Returns:
        List of pLDDT scores (0–100), one per residue (Cα atoms only).

    Raises:
        requests.HTTPError: On non-2xx HTTP responses.
        ValueError: If the PDB response cannot be parsed.
    """
    _api_key = api_key or os.getenv("BIONEMO_API_KEY", "")
    _api_base = (api_base or os.getenv("BIONEMO_API_BASE", _DEFAULT_API_BASE)).rstrip("/")

    url = f"{_api_base}/{_ESMFOLD_PATH}"
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if _api_key:
        headers["Authorization"] = f"Bearer {_api_key}"

    logger.debug("ESMFold NIM request: url={} seq_len={}", url, len(sequence))

    response = requests.post(
        url,
        json={"sequence": sequence},
        headers=headers,
        timeout=timeout,
    )
    response.raise_for_status()

    payload = response.json()
    pdb_string = _extract_pdb(payload)
    plddt = _parse_plddt_from_pdb(pdb_string)

    logger.info(
        "ESMFold: seq_len={} pLDDT mean={:.1f} min={:.1f} max={:.1f}",
        len(sequence),
        sum(plddt) / len(plddt) if plddt else 0,
        min(plddt) if plddt else 0,
        max(plddt) if plddt else 0,
    )
    return plddt


def mean_plddt(sequence: str, **kwargs) -> float:
    """Return the mean pLDDT for a sequence (convenience wrapper).

    Returns 0.0 on any error (safe for use in scoring pipelines).
    """
    try:
        scores = fold_sequence(sequence, **kwargs)
        return sum(scores) / len(scores) if scores else 0.0
    except Exception as exc:  # noqa: BLE001
        logger.debug("ESMFold mean_plddt failed: {}", exc)
        return 0.0


def get_pdb(
    sequence: str,
    *,
    api_key: str | None = None,
    api_base: str | None = None,
    timeout: int = _REQUEST_TIMEOUT,
) -> tuple[str, list[float]]:
    """Fold a sequence with ESMFold; return (pdb_string, plddt_list).

    Unlike ``fold_sequence`` which only returns pLDDT, this function returns
    the raw PDB string for 3D visualisation as well.

    Args:
        sequence: Amino acid sequence (standard 20 AAs).
        api_key: NVIDIA NIM API key.  Defaults to ``BIONEMO_API_KEY`` env var.
        api_base: NIM base URL.  Defaults to ``BIONEMO_API_BASE`` env var.
        timeout: HTTP request timeout in seconds.

    Returns:
        (pdb_string, plddt_list) — raw PDB text and per-residue pLDDT scores.

    Raises:
        requests.HTTPError: On non-2xx HTTP responses.
        ValueError: If the response cannot be parsed.
    """
    _api_key = api_key or os.getenv("BIONEMO_API_KEY", "")
    _api_base = (api_base or os.getenv("BIONEMO_API_BASE", _DEFAULT_API_BASE)).rstrip("/")

    url = f"{_api_base}/{_ESMFOLD_PATH}"
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if _api_key:
        headers["Authorization"] = f"Bearer {_api_key}"

    logger.debug("ESMFold NIM (get_pdb): url={} seq_len={}", url, len(sequence))

    response = requests.post(
        url,
        json={"sequence": sequence},
        headers=headers,
        timeout=timeout,
    )
    response.raise_for_status()

    payload = response.json()
    pdb_string = _extract_pdb(payload)
    plddt = _parse_plddt_from_pdb(pdb_string)

    logger.info(
        "ESMFold (get_pdb): seq_len={} residues={} mean_pLDDT={:.1f}",
        len(sequence),
        len(plddt),
        sum(plddt) / len(plddt) if plddt else 0,
    )
    return pdb_string, plddt


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_pdb(payload: dict) -> str:
    """Extract PDB string from ESMFold NIM response.

    Expected format: {"pdbs": ["<pdb content>", ...]}
    """
    if "pdbs" in payload and payload["pdbs"]:
        return payload["pdbs"][0]
    if "pdb" in payload:
        return payload["pdb"]
    raise ValueError(
        f"Unexpected ESMFold response format — "
        f"expected 'pdbs' key, got: {list(payload.keys())}"
    )


def _parse_plddt_from_pdb(pdb_string: str) -> list[float]:
    """Extract per-residue pLDDT from ESMFold PDB B-factor column (Cα only)."""
    matches = _PLDDT_RE.findall(pdb_string)
    if not matches:
        raise ValueError(
            "Could not parse pLDDT from PDB — no ATOM CA records found. "
            f"PDB preview: {pdb_string[:200]!r}"
        )
    return [float(v) for v in matches]
