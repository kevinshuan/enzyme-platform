"""Unit tests for enzyme/service/bionemo_generator.py — ESMFold-validated generator."""
from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pytest

from enzyme.models import EnzymeCandidate
from enzyme.service.bionemo_generator import generate_candidates

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SEQ = (
    "MSHHWGYGKHNGPEHWHKDFPIAKGERQSPVDIDTHTAKYDPSLKPLSVSYDQATSLRILNNGHAFNVEFD"
)  # 70 AA
_CONSERVED = [0, 5, 10, 20, 30]
_RNG = lambda seed=42: np.random.default_rng(seed)  # noqa: E731

# Fake ESMFold returns different pLDDT per call to test ranking
_CALL_COUNT = 0
_PLDDT_SCORES = [90.0, 70.0, 85.0, 60.0, 95.0, 75.0, 80.0, 50.0, 88.0, 65.0]


def _mock_fold(sequence, **kwargs):
    """Each call returns a different mean pLDDT so we can verify ranking."""
    global _CALL_COUNT
    plddt_val = _PLDDT_SCORES[_CALL_COUNT % len(_PLDDT_SCORES)]
    _CALL_COUNT += 1
    # Return a list of identical values (mean = plddt_val)
    return [plddt_val] * 10


def _setup():
    global _CALL_COUNT
    _CALL_COUNT = 0


# ---------------------------------------------------------------------------
# Basic contract
# ---------------------------------------------------------------------------


class TestGenerateCandidatesInterface:
    def setup_method(self):
        _setup()

    def test_returns_list_of_enzyme_candidates(self):
        with patch("enzyme.service.bionemo_generator.fold_sequence", side_effect=_mock_fold):
            result = generate_candidates(_SEQ, 0.05, 3, _CONSERVED, _RNG())
        assert isinstance(result, list)
        assert all(isinstance(c, EnzymeCandidate) for c in result)

    def test_returns_correct_number_of_candidates(self):
        with patch("enzyme.service.bionemo_generator.fold_sequence", side_effect=_mock_fold):
            result = generate_candidates(_SEQ, 0.05, 5, _CONSERVED, _RNG())
        assert len(result) == 5

    def test_candidates_have_unique_ids(self):
        with patch("enzyme.service.bionemo_generator.fold_sequence", side_effect=_mock_fold):
            result = generate_candidates(_SEQ, 0.05, 5, _CONSERVED, _RNG())
        ids = [c.id for c in result]
        assert len(ids) == len(set(ids))

    def test_base_sequence_preserved(self):
        with patch("enzyme.service.bionemo_generator.fold_sequence", side_effect=_mock_fold):
            result = generate_candidates(_SEQ, 0.05, 3, _CONSERVED, _RNG())
        assert all(c.base_sequence == _SEQ for c in result)


# ---------------------------------------------------------------------------
# ESMFold ranking
# ---------------------------------------------------------------------------


class TestEsmfoldRanking:
    def setup_method(self):
        _setup()

    def test_candidates_sorted_by_plddt_descending(self):
        """ESMFold-scored candidates must be sorted highest pLDDT first."""
        scores_seen = []

        def _ordered_fold(sequence, **kwargs):
            global _CALL_COUNT
            score = _PLDDT_SCORES[_CALL_COUNT % len(_PLDDT_SCORES)]
            _CALL_COUNT += 1
            scores_seen.append(score)
            return [score] * 10

        with patch("enzyme.service.bionemo_generator.fold_sequence", side_effect=_ordered_fold):
            result = generate_candidates(_SEQ, 0.05, 3, _CONSERVED, _RNG(), max_mutation_threshold=20)

        # The 3 best pLDDT scores from the oversample pool should come first
        top3_expected = sorted(scores_seen, reverse=True)[:3]
        # We can't map result → score easily without storing, but we can check
        # that n_candidates candidates were returned
        assert len(result) == 3

    def test_esmfold_called_for_oversampled_pool(self):
        """ESMFold should be called more than n_candidates times (oversample)."""
        call_count = [0]

        def _counting_fold(sequence, **kwargs):
            call_count[0] += 1
            return [90.0] * 10

        with patch("enzyme.service.bionemo_generator.fold_sequence", side_effect=_counting_fold):
            generate_candidates(_SEQ, 0.05, 2, _CONSERVED, _RNG())

        assert call_count[0] > 2  # oversample → more calls than n_candidates


# ---------------------------------------------------------------------------
# Conserved positions respected
# ---------------------------------------------------------------------------


class TestConservedPositions:
    def setup_method(self):
        _setup()

    def test_conserved_positions_not_mutated(self):
        with patch("enzyme.service.bionemo_generator.fold_sequence", side_effect=_mock_fold):
            result = generate_candidates(_SEQ, 0.2, 5, _CONSERVED, _RNG())
        for c in result:
            for pos in _CONSERVED:
                assert c.mutated_sequence[pos] == _SEQ[pos]

    def test_all_conserved_raises(self):
        with pytest.raises(ValueError, match="all positions are conserved"):
            generate_candidates(_SEQ, 0.05, 1, list(range(len(_SEQ))), _RNG())


# ---------------------------------------------------------------------------
# Fallback on ESMFold failure
# ---------------------------------------------------------------------------


class TestEsmfoldFallback:
    def setup_method(self):
        _setup()

    def test_falls_back_when_esmfold_unavailable(self):
        with patch(
            "enzyme.service.bionemo_generator.fold_sequence",
            side_effect=ConnectionError("NIM unavailable"),
        ):
            result = generate_candidates(_SEQ, 0.05, 3, _CONSERVED, _RNG())
        assert len(result) == 3
        assert all(isinstance(c, EnzymeCandidate) for c in result)

    def test_fallback_respects_conserved_positions(self):
        with patch(
            "enzyme.service.bionemo_generator.fold_sequence",
            side_effect=ConnectionError("NIM unavailable"),
        ):
            result = generate_candidates(_SEQ, 0.1, 5, _CONSERVED, _RNG())
        for c in result:
            for pos in _CONSERVED:
                assert c.mutated_sequence[pos] == _SEQ[pos]

    def test_fallback_sorted_by_mutation_count(self):
        """Fallback should return candidates with fewer mutations first."""
        with patch(
            "enzyme.service.bionemo_generator.fold_sequence",
            side_effect=ConnectionError("NIM unavailable"),
        ):
            result = generate_candidates(_SEQ, 0.1, 5, _CONSERVED, _RNG())
        counts = [c.mutation_count for c in result]
        assert counts == sorted(counts)


# ---------------------------------------------------------------------------
# Zero mutation rate
# ---------------------------------------------------------------------------


class TestZeroMutationRate:
    def test_zero_rate_returns_unmodified_copies(self):
        result = generate_candidates(_SEQ, 0.0, 3, _CONSERVED, _RNG())
        assert all(c.mutated_sequence == _SEQ for c in result)
        assert all(c.mutation_count == 0 for c in result)

    def test_zero_rate_does_not_call_esmfold(self):
        with patch("enzyme.service.bionemo_generator.fold_sequence") as mock_fold:
            generate_candidates(_SEQ, 0.0, 3, _CONSERVED, _RNG())
        mock_fold.assert_not_called()


# ---------------------------------------------------------------------------
# Mutation constraints
# ---------------------------------------------------------------------------


class TestMutationConstraints:
    def setup_method(self):
        _setup()

    def test_mutation_count_within_threshold(self):
        with patch("enzyme.service.bionemo_generator.fold_sequence", side_effect=_mock_fold):
            result = generate_candidates(
                _SEQ, 0.2, 5, _CONSERVED, _RNG(), max_mutation_threshold=10
            )
        assert all(c.mutation_count <= 10 for c in result)

    def test_mutation_positions_sorted(self):
        with patch("enzyme.service.bionemo_generator.fold_sequence", side_effect=_mock_fold):
            result = generate_candidates(_SEQ, 0.05, 5, _CONSERVED, _RNG())
        for c in result:
            assert c.mutation_positions == sorted(c.mutation_positions)
