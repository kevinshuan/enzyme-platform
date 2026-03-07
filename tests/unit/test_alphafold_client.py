"""Unit tests for enzyme/service/alphafold_client.py — AlphaFold DB API client."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from enzyme.service.alphafold_client import (
    fetch_alphafold_entry,
    fetch_conserved_positions,
    fetch_plddt,
    plddt_to_conserved_positions,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_FAKE_ENTRY = {
    "entryId": "AF-P00918-F1",
    "uniprotAccession": "P00918",
    "uniprotStart": 1,
    "uniprotEnd": 260,
    "plddtDocUrl": "https://alphafold.ebi.ac.uk/files/AF-P00918-F1-confidence_v6.json",
}

_FAKE_PLDDT = [95.0, 88.0, 92.0, 45.0, 71.0, 91.0]  # 6 residues


def _mock_get(url: str, **kwargs):
    """Return different mock responses depending on the URL."""
    mock = MagicMock()
    mock.raise_for_status = MagicMock()
    if "/api/prediction/" in url:
        mock.json.return_value = [_FAKE_ENTRY]
    elif "-confidence_" in url:
        mock.json.return_value = {"confidenceScore": _FAKE_PLDDT}
    return mock


# ---------------------------------------------------------------------------
# fetch_alphafold_entry
# ---------------------------------------------------------------------------


class TestFetchAlphafoldEntry:
    def test_returns_first_entry(self):
        with patch("requests.get", side_effect=_mock_get):
            entry = fetch_alphafold_entry("P00918")
        assert entry["entryId"] == "AF-P00918-F1"
        assert entry["uniprotAccession"] == "P00918"

    def test_raises_on_empty_response(self):
        mock = MagicMock()
        mock.raise_for_status = MagicMock()
        mock.json.return_value = []
        with patch("requests.get", return_value=mock):
            with pytest.raises(ValueError, match="No AlphaFold entry found"):
                fetch_alphafold_entry("INVALID")

    def test_raises_on_http_error(self):
        mock = MagicMock()
        mock.raise_for_status.side_effect = requests.HTTPError("404")
        with patch("requests.get", return_value=mock):
            with pytest.raises(requests.HTTPError):
                fetch_alphafold_entry("P00918")

    def test_calls_correct_url(self):
        with patch("requests.get", side_effect=_mock_get) as mock_get:
            fetch_alphafold_entry("P00918")
        call_url = mock_get.call_args_list[0][0][0]
        assert "prediction/P00918" in call_url


# ---------------------------------------------------------------------------
# fetch_plddt
# ---------------------------------------------------------------------------


class TestFetchPlddt:
    def test_returns_plddt_list(self):
        with patch("requests.get", side_effect=_mock_get):
            plddt = fetch_plddt("P00918")
        assert plddt == _FAKE_PLDDT

    def test_plddt_values_are_floats(self):
        with patch("requests.get", side_effect=_mock_get):
            plddt = fetch_plddt("P00918")
        assert all(isinstance(s, float) for s in plddt)

    def test_calls_confidence_url_from_entry(self):
        # Client must use plddtDocUrl from the entry, not a hardcoded version string
        with patch("requests.get", side_effect=_mock_get) as mock_get:
            fetch_plddt("P00918")
        urls = [call[0][0] for call in mock_get.call_args_list]
        assert any("AF-P00918-F1-confidence_v6" in url for url in urls)

    def test_uses_alphafold_id_from_entry(self):
        with patch("requests.get", side_effect=_mock_get) as mock_get:
            fetch_plddt("P00918")
        urls = [call[0][0] for call in mock_get.call_args_list]
        assert any("AF-P00918-F1" in url for url in urls)


# ---------------------------------------------------------------------------
# plddt_to_conserved_positions
# ---------------------------------------------------------------------------


class TestPlddtToConservedPositions:
    def test_default_threshold_90(self):
        # _FAKE_PLDDT = [95, 88, 92, 45, 71, 91] → indices 0, 2, 5 above 90
        result = plddt_to_conserved_positions(_FAKE_PLDDT)
        assert result == [0, 2, 5]

    def test_custom_threshold(self):
        # threshold=70 → indices 0, 1, 2, 4, 5
        result = plddt_to_conserved_positions(_FAKE_PLDDT, threshold=70.0)
        assert result == [0, 1, 2, 4, 5]

    def test_high_threshold_returns_empty(self):
        result = plddt_to_conserved_positions(_FAKE_PLDDT, threshold=99.0)
        assert result == []

    def test_zero_threshold_returns_all(self):
        result = plddt_to_conserved_positions(_FAKE_PLDDT, threshold=0.0)
        assert result == list(range(len(_FAKE_PLDDT)))

    def test_result_is_sorted(self):
        shuffled = [45.0, 95.0, 71.0, 92.0, 88.0, 91.0]
        result = plddt_to_conserved_positions(shuffled, threshold=90.0)
        assert result == sorted(result)

    def test_result_are_ints(self):
        result = plddt_to_conserved_positions(_FAKE_PLDDT)
        assert all(isinstance(i, int) for i in result)

    def test_boundary_value_excluded(self):
        # score == threshold should NOT be included (strict >)
        plddt = [90.0, 90.1, 89.9]
        result = plddt_to_conserved_positions(plddt, threshold=90.0)
        assert result == [1]


# ---------------------------------------------------------------------------
# fetch_conserved_positions (integration of entry + plddt + derivation)
# ---------------------------------------------------------------------------


class TestFetchConservedPositions:
    def test_end_to_end(self):
        with patch("requests.get", side_effect=_mock_get):
            positions = fetch_conserved_positions("P00918", threshold=90.0)
        assert positions == [0, 2, 5]

    def test_custom_threshold_propagated(self):
        with patch("requests.get", side_effect=_mock_get):
            positions = fetch_conserved_positions("P00918", threshold=70.0)
        assert positions == [0, 1, 2, 4, 5]

    def test_returns_sorted_list(self):
        with patch("requests.get", side_effect=_mock_get):
            positions = fetch_conserved_positions("P00918")
        assert positions == sorted(positions)
