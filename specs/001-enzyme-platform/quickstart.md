# Quickstart: AI-Designed Carbon-Reducing Enzyme Platform

**Branch**: `001-enzyme-platform` | **Date**: 2026-02-24

> **Note**: All scores are simulation proxies — not biological predictions or wet-lab results.

---

## Prerequisites

- Python 3.11+
- pip or conda

---

## Installation

```bash
# Clone and enter the repo
cd GPU-sequencing

# Install dependencies
pip install -r requirements.txt
```

**`requirements.txt`** (minimum):
```
fastapi==0.115.0
uvicorn[standard]==0.34.0
streamlit==1.42.0
pydantic==2.10.0
numpy>=1.26,<2.0        # version-locked for RNG reproducibility
pandas==2.2.0
plotly==5.24.0
requests==2.32.0
pytest==8.3.0
pytest-cov==6.0.0
```

---

## Configuration

### 1. Conserved Positions

Edit `config/conserved_regions.json` to specify amino acid positions (0-indexed) that MUST NOT
be mutated:

```json
{
  "conserved_positions": [5, 12, 18, 24, 31]
}
```

Restart the API after any change to this file.

### 2. Default Scoring Weights

Edit `config/weights.json` to change default scoring weights (must sum to 1.0):

```json
{
  "bio_weight": 0.3,
  "carbon_weight": 0.4,
  "feasibility_weight": 0.3,
  "max_mutation_threshold": 20
}
```

---

## Running the Platform

Open **two terminals** in the project root:

**Terminal 1 — API server**
```bash
uvicorn app.main:app --reload --port 8000
```

**Terminal 2 — Dashboard**
```bash
streamlit run dashboard/app.py
```

Open your browser at `http://localhost:8501` for the dashboard, or use the API directly at
`http://localhost:8000`.

---

## Quick API Test

```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "base_sequence": "MKTIIALSYIFCLVFADYKDDDKGSGYQSGDYHKSYNKSVEYAKHHK",
    "mutation_rate": 0.05,
    "candidates": 10,
    "seed": 42
  }'
```

Expected: JSON response with `ranked_candidates` array, sorted by `final_score` descending,
with `seed: 42` echoed back.

**Reproducibility check** — run the same command twice and confirm identical output:
```bash
# Both outputs should be byte-identical
curl -s ... | jq '.ranked_candidates[0].final_score'
curl -s ... | jq '.ranked_candidates[0].final_score'
```

---

## Running Tests

```bash
# All tests with coverage report
pytest --cov=. --cov-report=term-missing tests/

# Unit tests only (fast)
pytest tests/unit/

# Integration tests (requires API running)
pytest tests/integration/

# Boundary/performance tests
pytest tests/unit/ -m boundary
pytest tests/ -m benchmark --benchmark-only
```

Coverage target: **80%** across `generation/`, `scoring/`, `ranking/`.

---

## Project Structure

```
GPU-sequencing/
├── generation/
│   ├── __init__.py
│   ├── interface.py          # GeneratorInterface Protocol
│   └── mock_generator.py     # MVP mock (BioNeMo drop-in point)
├── scoring/
│   ├── __init__.py
│   ├── biological.py         # Kyte-Doolittle hydrophobicity scoring
│   ├── carbon.py             # Carbon impact proxy scoring
│   └── feasibility.py        # Commercial feasibility scoring
├── ranking/
│   ├── __init__.py
│   └── weighted.py           # Weighted + tie-break ranking
├── app/
│   ├── __init__.py
│   ├── main.py               # FastAPI entry point
│   ├── models.py             # Pydantic v2 request/response models
│   └── api.py                # Route handlers
├── dashboard/
│   └── app.py                # Streamlit dashboard
├── config/
│   ├── conserved_regions.json
│   └── weights.json
├── tests/
│   ├── conftest.py           # Session fixtures + shared sequences
│   ├── unit/
│   │   ├── test_generator.py
│   │   ├── test_biological.py
│   │   ├── test_carbon.py
│   │   ├── test_feasibility.py
│   │   └── test_ranking.py
│   └── integration/
│       └── test_api.py
├── specs/                    # Planning artifacts (not shipped)
└── requirements.txt
```

---

## Validation Checklist (run after any module change)

- [ ] `pytest tests/unit/` passes with 0 failures
- [ ] All scores confirmed in [0.0, 1.0] (`pytest tests/unit/ -k "normalization"`)
- [ ] Reproducibility check: same seed → identical output
- [ ] `/health` endpoint returns `{"status": "ok"}`
- [ ] Dashboard loads and renders all three charts
- [ ] CSV download produces a valid file with all candidates
