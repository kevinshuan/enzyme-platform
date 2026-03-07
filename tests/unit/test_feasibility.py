"""Unit tests for enzyme/service/scoring/feasibility.py — manufacturability scorer."""
from __future__ import annotations

import pytest

from enzyme.models import EnzymeCandidate
from enzyme.service.scoring.feasibility import (
    _EXPRESSION_CHALLENGING_AA,
    _MAX_CHALLENGING_FRACTION,
    compute_manufacturability,
    score_feasibility,
)

BASE = "ACDEFGHIKLMNPQRSTVWYACDEFGHIKLMNPQRSTVWYACDEFGHIKLMNPQRSTVWY"
NO_CHALLENGING = "ADEFGHIKLMNPQRSTADEFGHIKLMNPQRSTADEFGHIKLMNPQRSTADEGHIKLMNPQ"
ALL_CYS = "C" * 60
ALL_TRP = "W" * 60
AT_BOUNDARY = "C" * 12 + "A" * 48
UNDER_BOUNDARY = "C" * 11 + "A" * 49


def _make_candidate(
    base: str,
    mutated: str,
    positions: list[int],
    mutation_count: int | None = None,
) -> EnzymeCandidate:
    return EnzymeCandidate(
        id="test",
        base_sequence=base,
        mutated_sequence=mutated,
        mutation_positions=positions,
        mutation_count=mutation_count if mutation_count is not None else len(positions),
    )


class TestComputeManufacturability:
    def test_no_challenging_residues_returns_one(self):
        assert compute_manufacturability(NO_CHALLENGING) == pytest.approx(1.0)

    def test_all_cysteine_returns_zero(self):
        assert compute_manufacturability(ALL_CYS) == pytest.approx(0.0)

    def test_all_tryptophan_returns_zero(self):
        assert compute_manufacturability(ALL_TRP) == pytest.approx(0.0)

    def test_at_boundary_returns_zero(self):
        assert compute_manufacturability(AT_BOUNDARY) == pytest.approx(0.0)

    def test_under_boundary_positive(self):
        result = compute_manufacturability(UNDER_BOUNDARY)
        assert result > 0.0

    def test_output_in_unit_interval(self):
        for seq in [BASE, NO_CHALLENGING, ALL_CYS, ALL_TRP, AT_BOUNDARY, UNDER_BOUNDARY]:
            r = compute_manufacturability(seq)
            assert 0.0 <= r <= 1.0, f"Out of range for seq starting '{seq[:6]}'"

    def test_deterministic(self):
        assert compute_manufacturability(BASE) == compute_manufacturability(BASE)

    def test_independent_of_stability_score(self):
        import inspect
        sig = inspect.signature(compute_manufacturability)
        assert list(sig.parameters.keys()) == ["sequence"]

    def test_challenging_aa_set(self):
        assert _EXPRESSION_CHALLENGING_AA == frozenset("CW")

    def test_max_challenging_fraction_constant(self):
        assert _MAX_CHALLENGING_FRACTION == pytest.approx(0.20)

    def test_more_challenging_residues_lower_score(self):
        few_cys = "C" * 2 + "A" * 58
        many_cys = "C" * 10 + "A" * 50
        assert compute_manufacturability(few_cys) > compute_manufacturability(many_cys)

    def test_cys_and_trp_both_penalised(self):
        only_cys = "C" * 6 + "A" * 54
        only_trp = "W" * 6 + "A" * 54
        mixed = "C" * 3 + "W" * 3 + "A" * 54
        assert compute_manufacturability(only_cys) == pytest.approx(
            compute_manufacturability(only_trp)
        )
        assert compute_manufacturability(only_cys) == pytest.approx(
            compute_manufacturability(mixed)
        )


class TestScoreFeasibility:
    def test_no_mutations_no_challenging_residues_near_one(self):
        candidate = _make_candidate(NO_CHALLENGING, NO_CHALLENGING, [])
        score = score_feasibility(candidate, max_mutation_threshold=20)
        assert score == pytest.approx(1.0)

    def test_all_cysteine_sequence_low_score(self):
        candidate = _make_candidate(ALL_CYS, ALL_CYS, [])
        score = score_feasibility(candidate, max_mutation_threshold=20)
        assert score == pytest.approx(0.5)

    def test_output_in_unit_interval(self):
        for seq in [BASE, NO_CHALLENGING, ALL_CYS, ALL_TRP]:
            candidate = _make_candidate(BASE, seq, [])
            score = score_feasibility(candidate, max_mutation_threshold=20)
            assert 0.0 <= score <= 1.0

    def test_more_mutations_lower_score(self):
        few = _make_candidate(BASE, BASE, list(range(2)))
        many = _make_candidate(BASE, BASE, list(range(15)))
        score_few = score_feasibility(few, max_mutation_threshold=20)
        score_many = score_feasibility(many, max_mutation_threshold=20)
        assert score_few > score_many

    def test_challenging_sequence_lower_than_clean(self):
        clean = _make_candidate(BASE, NO_CHALLENGING, [])
        hard = _make_candidate(BASE, ALL_CYS, [])
        assert (
            score_feasibility(clean, max_mutation_threshold=20)
            > score_feasibility(hard, max_mutation_threshold=20)
        )

    def test_no_stability_score_parameter(self):
        import inspect
        sig = inspect.signature(score_feasibility)
        assert "stability_score" not in sig.parameters

    def test_score_is_deterministic(self):
        c = _make_candidate(BASE, BASE, [0])
        s1 = score_feasibility(c, max_mutation_threshold=20)
        s2 = score_feasibility(c, max_mutation_threshold=20)
        assert s1 == s2

    def test_mutation_count_at_threshold_difficulty_one(self):
        candidate = _make_candidate(BASE, BASE, [], mutation_count=20)
        score = score_feasibility(candidate, max_mutation_threshold=20)
        mfg = compute_manufacturability(BASE)
        assert score == pytest.approx(0.5 * mfg)

    def test_return_type_is_float(self):
        candidate = _make_candidate(BASE, BASE, [])
        assert isinstance(score_feasibility(candidate, max_mutation_threshold=20), float)
