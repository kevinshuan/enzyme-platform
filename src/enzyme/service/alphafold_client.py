"""AlphaFold DB API client — fetches per-residue pLDDT confidence scores.

AlphaFold DB provides AI-predicted 3D protein structures for 200M+ proteins.
pLDDT (per-residue confidence, 0–100) is used to derive conserved positions:
  - pLDDT > 90  → very high confidence → structurally critical → conserved
  - pLDDT 70–90 → high confidence
  - pLDDT 50–70 → low confidence
  - pLDDT < 50  → likely disordered → safe mutation target

Useful UniProt IDs for Carbonic Anhydrase:
  P00915 — Human Carbonic Anhydrase I  (CA I)
  P00918 — Human Carbonic Anhydrase II (CA II, most studied)
  P07451 — Human Carbonic Anhydrase III
"""
from __future__ import annotations

import requests
from loguru import logger

_ALPHAFOLD_API_BASE = "https://alphafold.ebi.ac.uk/api"
_REQUEST_TIMEOUT = 15  # seconds


def fetch_alphafold_entry(uniprot_id: str) -> dict:
    """Fetch AlphaFold DB entry metadata for a UniProt accession.

    Args:
        uniprot_id: UniProt accession (e.g., "P00918").

    Returns:
        First entry dict from the AlphaFold API response.

    Raises:
        requests.HTTPError: On non-2xx responses.
        ValueError: If no entry exists for the given UniProt ID.
    """
    url = f"{_ALPHAFOLD_API_BASE}/prediction/{uniprot_id}"
    response = requests.get(url, timeout=_REQUEST_TIMEOUT)
    response.raise_for_status()
    entries = response.json()
    if not entries:
        raise ValueError(f"No AlphaFold entry found for UniProt ID: {uniprot_id}")
    entry = entries[0]
    logger.info(
        "AlphaFold entry: uniprot_id={} alphafold_id={} length={}",
        uniprot_id,
        entry["entryId"],
        entry["uniprotEnd"] - entry["uniprotStart"] + 1,
    )
    return entry


def fetch_plddt(uniprot_id: str) -> list[float]:
    """Fetch per-residue pLDDT confidence scores from AlphaFold DB.

    Args:
        uniprot_id: UniProt accession (e.g., "P00918").

    Returns:
        List of pLDDT scores (0–100), one per residue.

    Raises:
        requests.HTTPError: On non-2xx responses.
        ValueError: If no entry exists for the given UniProt ID.
    """
    entry = fetch_alphafold_entry(uniprot_id)
    alphafold_id = entry["entryId"]

    # Use the URL directly from the API response — version-agnostic
    confidence_url = entry["plddtDocUrl"]
    response = requests.get(confidence_url, timeout=_REQUEST_TIMEOUT)
    response.raise_for_status()

    plddt: list[float] = response.json()["confidenceScore"]
    avg = sum(plddt) / len(plddt)
    high_frac = sum(1 for s in plddt if s > 90) / len(plddt)

    logger.info(
        "pLDDT fetched: alphafold_id={} residues={} avg={:.1f} high_conf_frac={:.2f}",
        alphafold_id,
        len(plddt),
        avg,
        high_frac,
    )
    return plddt


def plddt_to_conserved_positions(
    plddt: list[float],
    threshold: float = 90.0,
) -> list[int]:
    """Convert pLDDT scores to conserved (non-mutable) position indices.

    Residues above the threshold are structurally well-defined and should
    not be mutated. The default threshold of 90 corresponds to AlphaFold's
    "very high confidence" category.

    Args:
        plddt: Per-residue pLDDT scores (0–100).
        threshold: pLDDT value above which a residue is conserved.

    Returns:
        Sorted list of 0-indexed conserved position integers.
    """
    positions = sorted(i for i, score in enumerate(plddt) if score > threshold)
    logger.info(
        "Conserved positions derived: {}/{} residues above pLDDT threshold {:.0f}",
        len(positions),
        len(plddt),
        threshold,
    )
    return positions


def fetch_conserved_positions(
    uniprot_id: str,
    threshold: float = 90.0,
) -> list[int]:
    """Fetch AlphaFold pLDDT and return conserved positions in one call.

    Args:
        uniprot_id: UniProt accession (e.g., "P00918").
        threshold: pLDDT threshold (default 90 = "very high confidence").

    Returns:
        Sorted list of 0-indexed conserved position integers.
    """
    plddt = fetch_plddt(uniprot_id)
    return plddt_to_conserved_positions(plddt, threshold=threshold)
