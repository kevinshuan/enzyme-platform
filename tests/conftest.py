"""Shared pytest fixtures for the enzyme platform test suite."""
import pytest
import numpy as np


# 50-character valid amino acid sequence (minimum length per spec FR-002)
_SEQ_MINIMAL = "MKTIIALSYIFCLVFADYKDDDKGSGYQSGDYHKSYNKSVEYAKHHKMA"

# 100-character standard test sequence
_SEQ_STANDARD = (
    "MKTIIALSYIFCLVFADYKDDDKGSGYQSGDYHKSYNKSVEYAKHHKMA"
    "MKTIIALSYIFCLVFADYKDDDKGSGYQSGDYHKSYNKSVEYAKHHKMA"
)


@pytest.fixture(scope="session")
def test_sequence_minimal() -> str:
    """50-char valid amino acid sequence — minimum accepted by FR-002."""
    assert len(_SEQ_MINIMAL) == 50
    assert all(c in "ACDEFGHIKLMNPQRSTVWY" for c in _SEQ_MINIMAL)
    return _SEQ_MINIMAL


@pytest.fixture(scope="session")
def test_sequence_standard() -> str:
    """100-char valid amino acid sequence for standard scoring tests."""
    assert len(_SEQ_STANDARD) == 100
    assert all(c in "ACDEFGHIKLMNPQRSTVWY" for c in _SEQ_STANDARD)
    return _SEQ_STANDARD


@pytest.fixture(scope="session")
def test_conserved_positions() -> list[int]:
    """Conserved positions matching config/conserved_regions.json placeholder."""
    return [5, 12, 18, 24, 31]


@pytest.fixture(scope="session")
def test_default_weights() -> dict:
    """Default scoring weights per spec FR-010."""
    return {"bio_weight": 0.3, "carbon_weight": 0.4, "feasibility_weight": 0.3}


@pytest.fixture(scope="session")
def fixed_seed() -> int:
    """Fixed seed for reproducibility tests (US3)."""
    return 42


@pytest.fixture
def fixed_rng(fixed_seed) -> np.random.Generator:
    """Fresh seeded Generator for each test function."""
    return np.random.default_rng(fixed_seed)
