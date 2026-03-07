"""Unit tests for enzyme/service/bionemo_client.py — NVIDIA NIM ESMFold client."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from enzyme.service.bionemo_client import (
    _extract_pdb,
    _parse_plddt_from_pdb,
    fold_sequence,
    mean_plddt,
)

# ---------------------------------------------------------------------------
# Minimal PDB fixture with known pLDDT values
# ---------------------------------------------------------------------------

_PDB_TEMPLATE = """\
PARENT N/A
MODEL     1
ATOM      1  N   MET A   1      -8.953  -5.599 -14.173  1.00 {p0:.2f}           N
ATOM      2  CA  MET A   1      -8.133  -6.011 -12.990  1.00 {p0:.2f}           C
ATOM      3  C   MET A   1      -8.881  -6.713 -11.843  1.00 {p0:.2f}           C
ATOM      4  N   SER A   2      -8.123  -7.402 -10.990  1.00 {p1:.2f}           N
ATOM      5  CA  SER A   2      -8.623  -8.012  -9.780  1.00 {p1:.2f}           C
ATOM      6  C   SER A   2      -9.403  -7.112  -8.870  1.00 {p1:.2f}           C
ATOM      7  N   HIS A   3      -9.103  -6.812  -7.600  1.00 {p2:.2f}           N
ATOM      8  CA  HIS A   3      -9.773  -5.982  -6.612  1.00 {p2:.2f}           C
TER
ENDMDL
"""

_FAKE_PLDDT = [85.5, 92.3, 78.1]  # one per CA per residue


def _make_pdb(scores=None):
    if scores is None:
        scores = _FAKE_PLDDT
    return _PDB_TEMPLATE.format(p0=scores[0], p1=scores[1], p2=scores[2])


def _mock_post_esmfold(url, **kwargs):
    mock = MagicMock()
    mock.raise_for_status = MagicMock()
    mock.json.return_value = {"pdbs": [_make_pdb()]}
    return mock


# ---------------------------------------------------------------------------
# _extract_pdb
# ---------------------------------------------------------------------------


class TestExtractPdb:
    def test_extracts_from_pdbs_list(self):
        payload = {"pdbs": ["ATOM 1 ...", "other"]}
        assert _extract_pdb(payload) == "ATOM 1 ..."

    def test_extracts_from_pdb_key(self):
        payload = {"pdb": "ATOM 2 ..."}
        assert _extract_pdb(payload) == "ATOM 2 ..."

    def test_raises_on_unknown_format(self):
        with pytest.raises(ValueError, match="Unexpected ESMFold"):
            _extract_pdb({"result": "something"})

    def test_raises_on_empty_pdbs(self):
        with pytest.raises((ValueError, IndexError)):
            _extract_pdb({"pdbs": []})


# ---------------------------------------------------------------------------
# _parse_plddt_from_pdb
# ---------------------------------------------------------------------------


class TestParsePlddtFromPdb:
    def test_extracts_correct_number_of_residues(self):
        pdb = _make_pdb()
        scores = _parse_plddt_from_pdb(pdb)
        assert len(scores) == 3  # 3 Cα atoms

    def test_extracts_correct_values(self):
        pdb = _make_pdb()
        scores = _parse_plddt_from_pdb(pdb)
        assert scores == pytest.approx(_FAKE_PLDDT, abs=0.01)

    def test_all_values_in_valid_range(self):
        pdb = _make_pdb()
        scores = _parse_plddt_from_pdb(pdb)
        assert all(0.0 <= s <= 100.0 for s in scores)

    def test_raises_on_empty_pdb(self):
        with pytest.raises(ValueError, match="pLDDT"):
            _parse_plddt_from_pdb("HEADER  Empty structure\nEND")

    def test_returns_floats(self):
        pdb = _make_pdb()
        scores = _parse_plddt_from_pdb(pdb)
        assert all(isinstance(s, float) for s in scores)


# ---------------------------------------------------------------------------
# fold_sequence
# ---------------------------------------------------------------------------


class TestFoldSequence:
    _SEQ = "MSHHWGYGKHNGPEHWHKDFPIAKGER"

    def test_returns_plddt_list(self):
        with patch("requests.post", side_effect=_mock_post_esmfold):
            result = fold_sequence(self._SEQ, api_key="test")
        assert result == pytest.approx(_FAKE_PLDDT, abs=0.01)

    def test_plddt_values_are_floats(self):
        with patch("requests.post", side_effect=_mock_post_esmfold):
            result = fold_sequence(self._SEQ, api_key="test")
        assert all(isinstance(s, float) for s in result)

    def test_raises_on_http_error(self):
        mock = MagicMock()
        mock.raise_for_status.side_effect = requests.HTTPError("500")
        with patch("requests.post", return_value=mock):
            with pytest.raises(requests.HTTPError):
                fold_sequence(self._SEQ, api_key="test")

    def test_authorization_header_sent(self):
        with patch("requests.post", side_effect=_mock_post_esmfold) as mock_post:
            fold_sequence(self._SEQ, api_key="nvapi-abc123")
        headers = mock_post.call_args[1]["headers"]
        assert headers["Authorization"] == "Bearer nvapi-abc123"

    def test_no_auth_header_when_no_key(self):
        with patch("requests.post", side_effect=_mock_post_esmfold) as mock_post:
            with patch.dict("os.environ", {"BIONEMO_API_KEY": ""}, clear=False):
                fold_sequence(self._SEQ, api_key="")
        headers = mock_post.call_args[1]["headers"]
        assert "Authorization" not in headers

    def test_custom_api_base_used(self):
        with patch("requests.post", side_effect=_mock_post_esmfold) as mock_post:
            fold_sequence(self._SEQ, api_base="http://localhost:8080/v1")
        url = mock_post.call_args[0][0]
        assert "localhost:8080" in url

    def test_sequence_sent_in_payload(self):
        with patch("requests.post", side_effect=_mock_post_esmfold) as mock_post:
            fold_sequence(self._SEQ, api_key="test")
        payload = mock_post.call_args[1]["json"]
        assert payload["sequence"] == self._SEQ

    def test_calls_esmfold_endpoint(self):
        with patch("requests.post", side_effect=_mock_post_esmfold) as mock_post:
            fold_sequence(self._SEQ, api_key="test")
        url = mock_post.call_args[0][0]
        assert "esmfold" in url


# ---------------------------------------------------------------------------
# mean_plddt
# ---------------------------------------------------------------------------


class TestMeanPlddt:
    _SEQ = "MSHHWGYGKHNGPEHWHKDFPIAKGER"

    def test_returns_mean_of_plddt_scores(self):
        with patch("requests.post", side_effect=_mock_post_esmfold):
            result = mean_plddt(self._SEQ, api_key="test")
        expected = sum(_FAKE_PLDDT) / len(_FAKE_PLDDT)
        assert result == pytest.approx(expected, abs=0.01)

    def test_returns_zero_on_api_error(self):
        mock = MagicMock()
        mock.raise_for_status.side_effect = requests.HTTPError("500")
        with patch("requests.post", return_value=mock):
            result = mean_plddt(self._SEQ, api_key="test")
        assert result == pytest.approx(0.0)

    def test_returns_float(self):
        with patch("requests.post", side_effect=_mock_post_esmfold):
            result = mean_plddt(self._SEQ, api_key="test")
        assert isinstance(result, float)
