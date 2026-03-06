"""Unit tests for scoring/biological.py — BLOSUM62-based stability scorer."""
from __future__ import annotations

import pytest

from app.models import EnzymeCandidate
from scoring.biological import (
    BLOSUM62,
    _BLOSUM62_SUB_MIN,
    _BLOSUM62_SUB_MAX,
    _BLOSUM62_SUB_RANGE,
    compute_blosum62_stability,
    score_biological,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BASE = "ACDEFGHIKLMNPQRSTVWYACDEFGHIKLMNPQRSTVWYACDEFGHIKLMNPQRSTVWY"  # 60 aa


def _make_candidate(
    base: str,
    mutated: str,
    positions: list[int],
) -> EnzymeCandidate:
    return EnzymeCandidate(
        id="test",
        base_sequence=base,
        mutated_sequence=mutated,
        mutation_positions=positions,
        mutation_count=len(positions),
    )


# ---------------------------------------------------------------------------
# compute_blosum62_stability — direct unit tests
# ---------------------------------------------------------------------------


class TestComputeBlosum62Stability:
    def test_no_mutations_returns_one(self):
        assert compute_blosum62_stability(BASE, BASE, []) == 1.0

    def test_conservative_i_to_v(self):
        # I→V: BLOSUM62 score = 3  →  normalized = (3 + 4) / 7 = 1.0
        base = "I" + "A" * 59
        mut = "V" + "A" * 59
        result = compute_blosum62_stability(base, mut, [0])
        assert result == pytest.approx(1.0)

    def test_radical_w_to_r(self):
        # W→R: BLOSUM62 score = -3  →  normalized = (-3 + 4) / 7 ≈ 0.1429
        base = "W" + "A" * 59
        mut = "R" + "A" * 59
        result = compute_blosum62_stability(base, mut, [0])
        assert result == pytest.approx(1 / 7, rel=1e-4)

    def test_mean_of_multiple_mutations(self):
        # I→V (norm=1.0) and W→R (norm=1/7) → mean = (1.0 + 1/7) / 2
        base = "IW" + "A" * 58
        mut = "VR" + "A" * 58
        result = compute_blosum62_stability(base, mut, [0, 1])
        expected = (1.0 + 1 / 7) / 2
        assert result == pytest.approx(expected, rel=1e-4)

    def test_output_in_unit_interval(self):
        # Worst possible substitution should still be >= 0
        base = "W" + "A" * 59
        mut = "R" + "A" * 59
        result = compute_blosum62_stability(base, mut, [0])
        assert 0.0 <= result <= 1.0

    def test_normalization_constants(self):
        assert _BLOSUM62_SUB_MIN == -4
        assert _BLOSUM62_SUB_MAX == 3
        assert _BLOSUM62_SUB_RANGE == 7


# ---------------------------------------------------------------------------
# score_biological — integration tests
# ---------------------------------------------------------------------------


class TestScoreBiological:
    def test_zero_mutations_score_near_one(self):
        candidate = _make_candidate(BASE, BASE, [])
        score = score_biological(candidate, conserved_positions=[])
        # stability=1.0, mutation_pen=0, conserved_pen=0 → 0.4+0.4+0.2 = 1.0
        assert score == pytest.approx(1.0)

    def test_conservative_mutation_high_score(self):
        # Replace position 7 (I in ACDEFGHI…) with V
        pos = 7  # BASE[7] == 'I'
        mut = BASE[:pos] + "V" + BASE[pos + 1 :]
        candidate = _make_candidate(BASE, mut, [pos])
        score = score_biological(candidate, conserved_positions=[])
        # stability ≈ 1.0, mutation_pen = 1/60 ≈ 0.017, conserved_pen = 0
        # bio_score ≈ 0.4*1.0 + 0.4*(1-0.017) + 0.2*1.0 ≈ 0.993
        assert score > 0.95

    def test_radical_mutation_lower_score(self):
        # W is at position 19 in BASE (0-indexed)
        pos = 19  # BASE[19] == 'W'
        mut = BASE[:pos] + "R" + BASE[pos + 1 :]
        candidate = _make_candidate(BASE, mut, [pos])
        conservative_candidate = _make_candidate(
            BASE, BASE[:7] + "V" + BASE[8:], [7]
        )
        radical_score = score_biological(candidate, conserved_positions=[])
        conservative_score = score_biological(conservative_candidate, conserved_positions=[])
        assert radical_score < conservative_score

    def test_output_range_is_unit_interval(self):
        # High mutation count scenario
        positions = list(range(0, 20, 2))  # 10 mutations
        mut = list(BASE)
        replacements = "RRRRRRRRRRRRRRRRRRRRR"
        for i, pos in enumerate(positions):
            mut[pos] = replacements[i]
        candidate = _make_candidate(BASE, "".join(mut), positions)
        score = score_biological(candidate, conserved_positions=[])
        assert 0.0 <= score <= 1.0

    def test_conserved_penalty_reduces_score(self):
        pos = 7  # 'I' → 'V'
        mut = BASE[:pos] + "V" + BASE[pos + 1 :]

        score_no_conserved = score_biological(
            _make_candidate(BASE, mut, [pos]),
            conserved_positions=[],
        )
        score_with_conserved = score_biological(
            _make_candidate(BASE, mut, [pos]),
            conserved_positions=[pos],
        )
        assert score_with_conserved < score_no_conserved

    def test_score_is_float_in_range(self):
        pos = 0  # 'A' → 'C'
        mut = "C" + BASE[1:]
        candidate = _make_candidate(BASE, mut, [pos])
        score = score_biological(candidate, conserved_positions=[])
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# BLOSUM62 matrix sanity checks
# ---------------------------------------------------------------------------


class TestBlosum62Matrix:
    def test_all_standard_amino_acids_present(self):
        aa = set("ACDEFGHIKLMNPQRSTVWY")
        assert set(BLOSUM62.keys()) == aa
        for row in BLOSUM62.values():
            assert set(row.keys()) == aa

    def test_symmetry(self):
        for a in BLOSUM62:
            for b in BLOSUM62:
                assert BLOSUM62[a][b] == BLOSUM62[b][a], f"Asymmetry: {a}↔{b}"

    def test_i_v_score_is_3(self):
        assert BLOSUM62["I"]["V"] == 3

    def test_w_r_score_is_minus_3(self):
        assert BLOSUM62["W"]["R"] == -3
