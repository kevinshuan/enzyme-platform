# Research: AI-Designed Carbon-Reducing Enzyme Platform

**Branch**: `001-enzyme-platform` | **Date**: 2026-02-24
**Phase**: 0 — Research & Decision Resolution

---

## 1. NumPy Random Number Generation (Reproducibility)

**Decision**: Use `np.random.default_rng(seed)` with the `Generator` object passed as a parameter
through all function calls.

**Rationale**: `default_rng` with PCG64 is platform-identical (Windows/Linux/macOS) for the same
seed on the same NumPy version — exactly 2-10× faster than legacy `RandomState`. Legacy
`np.random.seed()` is frozen to NumPy v1.16 semantics and discouraged for new code. Neither
approach guarantees cross-version bit identity, so the NumPy version MUST be pinned in
`requirements.txt`.

**Alternatives considered**:
- `np.random.seed()` + global state — rejected: global mutable state breaks independent
  testability (Constitution Principle I) and is slower.
- Creating a new `Generator` inside each function — rejected: breaks reproducibility because
  each call re-initialises the RNG state.

**Concrete pattern**:
```python
# Entry point: create once
rng = np.random.default_rng(seed=user_seed)  # None = non-deterministic

# Worker functions: receive rng as parameter
def generate_candidates(..., rng: np.random.Generator) -> list[EnzymeCandidate]:
    pos = rng.integers(0, len(sequence))          # integer position
    aa  = rng.choice(AMINO_ACIDS)                 # amino acid selection
```

**Version lock**: Pin `numpy>=1.26,<2.0` in `requirements.txt` for stable PCG64 output.

---

## 2. Hydrophobicity Formula Correction (Critical Bug in Spec)

**Decision**: Divide the absolute hydrophobicity difference by 9.0 (the Kyte-Doolittle scale
range) before subtracting from 1.0.

**Rationale**: The Kyte-Doolittle (1982) scale spans −4.5 (Arginine) to +4.5 (Isoleucine),
a total range of 9.0. The spec formula `stability_score = 1 - abs(Δhydro)` is **broken** — the
raw difference can reach 9.0, producing scores as low as −8.0, violating Score Integrity
(Constitution Principle II). Dividing by 9.0 guarantees output ∈ [0, 1].

**Corrected formula**:
```python
HYDRO_SCALE = 9.0  # max(KD) - min(KD) = 4.5 - (-4.5)

stability_score = 1.0 - (abs(mean_hydro_orig - mean_hydro_mut) / HYDRO_SCALE)
stability_score = max(0.0, min(1.0, stability_score))  # clamp for float safety
```

**Kyte-Doolittle index (all 20 amino acids)**:
```python
KYTE_DOOLITTLE = {
    'A':  1.8, 'C':  2.5, 'D': -3.5, 'E': -3.5, 'F':  2.8,
    'G': -0.4, 'H': -3.2, 'I':  4.5, 'K': -3.9, 'L':  3.8,
    'M':  1.9, 'N': -3.5, 'P': -1.6, 'Q': -3.5, 'R': -4.5,
    'S': -0.8, 'T': -0.7, 'V':  4.2, 'W': -0.9, 'Y': -1.3,
}
```

**Alternatives considered**:
- Min-max normalise per-sequence — rejected: breaks comparability across candidates with
  different base sequences.
- Use a different hydrophobicity scale (Eisenberg, Hopp-Woods) — rejected: Kyte-Doolittle is
  the most widely cited and specified in the original brief; change requires documented rationale
  per Constitution Principle V.

---

## 3. FastAPI + Streamlit Communication Pattern

**Decision**: Streamlit calls FastAPI via HTTP using the `requests` library. Two separate
terminals for local development.

**Rationale**: HTTP separation keeps each component independently runnable and testable (Principle
I). It mirrors future deployment topology (API on a server, dashboard on a client), and the
~5–50 ms local latency is negligible for this use case. Direct Python import coupling would make
the generation → scoring → API chain inseparable and break independent testability.

**Alternatives considered**:
- Direct Python module imports in Streamlit — rejected: tight coupling; breaks constitution gates
  for independent module testability.
- Subprocess orchestration (run both from one script) — rejected: adds process management
  complexity for no gain in a dev workflow; YAGNI.

**Development setup**:
```bash
# Terminal 1 — API
uvicorn app.main:app --reload --port 8000

# Terminal 2 — Dashboard
streamlit run dashboard/app.py
```

**Streamlit CSV export pattern**:
```python
import pandas as pd
from io import StringIO

csv = pd.DataFrame(candidates).to_csv(index=False)
st.download_button("Download CSV", csv, "candidates.csv", "text/csv")
```

**Pydantic v2 key differences from v1**:

| v1 | v2 |
|----|-----|
| `class Config:` | `model_config = ConfigDict(...)` |
| `@validator` | `@field_validator` (+ `@classmethod`) |
| `.dict()` | `.model_dump()` |
| `.schema()` | `.model_json_schema()` |

---

## 4. pytest Patterns for Numerical Scoring

**Decision**: Use `numpy.testing.assert_array_equal` for byte-identical reproducibility
assertions; session-scoped conftest fixtures for shared sequences; `@pytest.mark.parametrize`
with descriptive IDs for boundary tests.

**Rationale**: `assert_array_equal` performs bit-level float comparison (not approximate),
satisfying the "byte-identical" requirement from FR-011/SC-004. Session fixtures load test
sequences once per run, keeping tests fast. Parametrize with IDs (`no-mutations`, `max-rate`,
etc.) produces readable failure messages.

**Score range assertion pattern**:
```python
import numpy as np

def assert_score_in_range(score: float, label: str = "") -> None:
    assert 0.0 <= score <= 1.0, f"{label}: {score} out of [0, 1]"

# Batch validation:
np.testing.assert_array_less(-1e-10, scores_array)
np.testing.assert_array_less(scores_array, 1.0 + 1e-10)
```

**Byte-identical reproducibility assertion**:
```python
import numpy as np

scores_run1 = np.array([c.final_score for c in run1], dtype=np.float64)
scores_run2 = np.array([c.final_score for c in run2], dtype=np.float64)
np.testing.assert_array_equal(scores_run1, scores_run2)
```

**Coverage target**: 80% per spec. Use `pytest-cov`:
```bash
pytest --cov=. --cov-report=term-missing tests/
```

**Additional recommended packages**: `pytest-benchmark` for SC-002 (<3 s for 500 candidates).

---

## 5. Resolved NEEDS CLARIFICATION Items

All items were resolved during `/speckit.clarify`. Summary for traceability:

| Item | Decision |
|------|----------|
| Data persistence | Stateless — results in response only |
| Result export | CSV download button in dashboard |
| API access control | None — localhost only, no auth in MVP |
| Tie-breaking rule | Biological score descending |
| Conservation map management | File edit only (`config/conserved_regions.json`) |
