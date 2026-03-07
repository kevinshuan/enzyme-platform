"""Unit tests for enzyme/service/scoring/carbon.py — deterministic sequence-based carbon scorer."""
from __future__ import annotations

import pytest

from enzyme.models import EnzymeCandidate
from enzyme.service.scoring.carbon import (
    _MAX_CHARGE_PER_RESIDUE,
    _POLAR_AA,
    compute_charge_neutrality,
    compute_co2_efficiency,
    compute_polar_fraction,
    score_carbon,
)

BASE = "ACDEFGHIKLMNPQRSTVWYACDEFGHIKLMNPQRSTVWYACDEFGHIKLMNPQRSTVWY"
ALL_POLAR = "STNQDEKRHY" * 6
ALL_NONPOLAR = "ACFGILMPVW" * 6
ALL_LYS = "K" * 60
ALL_GLU = "E" * 60
BALANCED_CHARGE = "KE" * 30


def _make_candidate(base: str, mutated: str, positions: list[int]) -> EnzymeCandidate:
    return EnzymeCandidate(
        id="test",
        base_sequence=base,
        mutated_sequence=mutated,
        mutation_positions=positions,
        mutation_count=len(positions),
    )


class TestComputePolarFraction:
    def test_all_polar_returns_one(self):
        assert compute_polar_fraction(ALL_POLAR) == pytest.approx(1.0)

    def test_all_nonpolar_returns_zero(self):
        assert compute_polar_fraction(ALL_NONPOLAR) == pytest.approx(0.0)

    def test_mixed_sequence_in_unit_interval(self):
        result = compute_polar_fraction(BASE)
        assert 0.0 <= result <= 1.0

    def test_polar_aa_set_covers_expected_residues(self):
        assert _POLAR_AA == frozenset("STNQDEKRHY")

    def test_determinism(self):
        assert compute_polar_fraction(BASE) == compute_polar_fraction(BASE)


class TestComputeChargeNeutrality:
    def test_all_lysine_is_zero(self):
        assert compute_charge_neutrality(ALL_LYS) == pytest.approx(0.0)

    def test_all_glutamate_is_zero(self):
        assert compute_charge_neutrality(ALL_GLU) == pytest.approx(0.0)

    def test_balanced_ke_near_one(self):
        result = compute_charge_neutrality(BALANCED_CHARGE)
        assert result == pytest.approx(1.0, abs=1e-6)

    def test_output_in_unit_interval(self):
        for seq in [BASE, ALL_POLAR, ALL_NONPOLAR, ALL_LYS, ALL_GLU]:
            result = compute_charge_neutrality(seq)
            assert 0.0 <= result <= 1.0, f"Out of range for seq starting {seq[:6]}"

    def test_determinism(self):
        assert compute_charge_neutrality(BASE) == compute_charge_neutrality(BASE)

    def test_max_charge_constant(self):
        assert _MAX_CHARGE_PER_RESIDUE == pytest.approx(0.5)


class TestComputeCo2Efficiency:
    def test_output_in_unit_interval_for_various_sequences(self):
        for seq in [BASE, ALL_POLAR, ALL_NONPOLAR, ALL_LYS, ALL_GLU, BALANCED_CHARGE]:
            result = compute_co2_efficiency(seq)
            assert 0.0 <= result <= 1.0, f"Out of range for {seq[:6]}"

    def test_is_mean_of_components(self):
        polar = compute_polar_fraction(BASE)
        neutrality = compute_charge_neutrality(BASE)
        expected = (polar + neutrality) / 2.0
        assert compute_co2_efficiency(BASE) == pytest.approx(expected)

    def test_fully_deterministic_same_sequence(self):
        r1 = compute_co2_efficiency(BASE)
        r2 = compute_co2_efficiency(BASE)
        assert r1 == r2

    def test_different_sequences_can_differ(self):
        assert compute_co2_efficiency(ALL_POLAR) != compute_co2_efficiency(ALL_NONPOLAR)


class TestScoreCarbon:
    def test_score_is_deterministic(self):
        candidate = _make_candidate(BASE, BASE, [])
        s1 = score_carbon(candidate, stability_score=0.8)
        s2 = score_carbon(candidate, stability_score=0.8)
        assert s1 == s2

    def test_score_in_unit_interval(self):
        candidate = _make_candidate(BASE, BASE, [])
        score = score_carbon(candidate, stability_score=0.8)
        assert 0.0 <= score <= 1.0

    def test_same_sequence_different_order_same_score(self):
        c1 = _make_candidate(BASE, BASE, [])
        c2 = _make_candidate(BASE, BASE, [])
        assert score_carbon(c1, stability_score=0.7) == score_carbon(c2, stability_score=0.7)

    def test_high_stability_raises_score(self):
        candidate = _make_candidate(BASE, BASE, [])
        low = score_carbon(candidate, stability_score=0.1)
        high = score_carbon(candidate, stability_score=0.9)
        assert high > low

    def test_many_mutations_lowers_score(self):
        few_mut = _make_candidate(BASE, BASE[:1] + "V" + BASE[2:], [1])
        many_mut = EnzymeCandidate(
            id="many",
            base_sequence=BASE,
            mutated_sequence=BASE,
            mutation_positions=list(range(50)),
            mutation_count=50,
        )
        score_few = score_carbon(few_mut, stability_score=0.8)
        score_many = score_carbon(many_mut, stability_score=0.8)
        assert score_few > score_many

    def test_score_depends_on_mutated_sequence(self):
        c_polar = _make_candidate(BASE, ALL_POLAR, [])
        c_nonpolar = _make_candidate(BASE, ALL_NONPOLAR, [])
        assert (
            score_carbon(c_polar, stability_score=0.8)
            != score_carbon(c_nonpolar, stability_score=0.8)
        )

    def test_zero_mutations_no_production_cost_penalty(self):
        candidate = _make_candidate(BASE, BASE, [])
        efficiency = compute_co2_efficiency(BASE)
        stability = 0.9
        expected_raw = (efficiency * stability) - 0.0
        expected_score = max(0.0, min(1.0, (expected_raw + 1.0) / 2.0))
        assert score_carbon(candidate, stability_score=stability) == pytest.approx(expected_score)

    def test_return_type_is_float(self):
        candidate = _make_candidate(BASE, BASE, [])
        assert isinstance(score_carbon(candidate, stability_score=0.5), float)
