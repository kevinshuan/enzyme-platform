# AI-Designed Carbon-Reducing Enzyme Platform

A modular pipeline that generates mutated Carbonic Anhydrase-like enzyme candidates,
scores them across three dimensions, ranks them, and exposes results via a REST API
and interactive Streamlit dashboard.

> **Disclaimer**: All scores are simulation proxies. No wet-lab validation has been
> performed. This is an MVP mock generator designed for drop-in replacement with
> NVIDIA BioNeMo inference in Phase 2.

---

## Quickstart

### 1 — Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2 — Start the API (Terminal 1)

```bash
uvicorn app.main:app --port 8000 --reload
```

### 3 — Start the dashboard (Terminal 2)

```bash
streamlit run dashboard/app.py
```

Open your browser at `http://localhost:8501`.

---

## API Example

```bash
curl -s -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "base_sequence": "ACDEFGHIKLMNPQRSTVWYACDEFGHIKLMNPQRSTVWYACDEFGHIKLMNPQRSTVWY",
    "mutation_rate": 0.05,
    "candidates": 10,
    "seed": 42
  }' | python -m json.tool
```

**Response shape**:
```json
{
  "seed": 42,
  "total_generated": 10,
  "weights_used": {"bio_weight": 0.3, "carbon_weight": 0.4, "feasibility_weight": 0.3},
  "ranked_candidates": [
    {
      "id": "...",
      "mutated_sequence": "...",
      "mutation_positions": [2, 7, 14],
      "mutation_count": 3,
      "bio_score": 0.8312,
      "carbon_score": 0.6741,
      "feasibility_score": 0.7500,
      "final_score": 0.7449
    }
  ],
  "_meta": {
    "disclaimer": "All scores are simulation proxies. Not wet-lab validated predictions.",
    "sort_order": "final_score DESC, bio_score DESC on tie"
  }
}
```

**Reproduce exact results**: pass `"seed": <value>` from a previous response.

---

## Configuration

| File | Purpose |
|------|---------|
| `config/conserved_regions.json` | 0-indexed positions that must not be mutated |
| `config/weights.json` | Default scoring weights and `max_mutation_threshold` |

Edit these files to adjust defaults without touching code.

---

## Architecture

```
POST /generate
  └── validate sequence
  └── np.random.default_rng(seed)   ← single RNG for full reproducibility
  └── generate_candidates()         ← mock_generator.py  (swap for BioNeMo)
  └── score_biological()            ← Kyte-Doolittle hydrophobicity
  └── score_carbon()                ← efficiency / deployment / cost proxy
  └── score_feasibility()           ← difficulty + manufacturability
  └── rank_candidates()             ← final_score DESC, bio_score DESC on tie
  └── GenerateResponse
```

**BioNeMo replacement**: swap `generation/mock_generator.py` for a class that
implements `generation/interface.py:GeneratorInterface`. No other files change.

---

## Scoring Formulas

### Biological (`scoring/biological.py`)
```
stability      = 1 − |mean_hydro(base) − mean_hydro(mutated)| / 9.0
mutation_pen   = mutation_count / len(sequence)
conserved_pen  = mutations_in_conserved / mutation_count
bio_score      = 0.4·stability + 0.4·(1−mutation_pen) + 0.2·(1−conserved_pen)
```

### Carbon impact (`scoring/carbon.py`)
```
efficiency_gain  = rng.uniform(0.9, 1.2)          # CO₂ conversion proxy
norm_efficiency  = (efficiency_gain − 0.9) / 0.3
production_cost  = min(1.0, mutation_count × 0.01)
raw              = norm_efficiency × stability − production_cost
carbon_score     = (raw + 1.0) / 2.0              # rescale [−1,1] → [0,1]
```

### Commercial feasibility (`scoring/feasibility.py`)
```
difficulty         = mutation_count / max_mutation_threshold
manufacturability  = stability
feasibility_score  = 0.5·(1−difficulty) + 0.5·manufacturability
```

---

## Testing

```bash
pytest --cov=. --cov-report=term-missing
```

Coverage target: ≥ 80 %

---

## Project structure

```
GPU-sequencing/
├── app/
│   ├── api.py              # FastAPI router (POST /generate, GET /health)
│   ├── config_loader.py    # JSON config reader
│   ├── main.py             # FastAPI app + lifespan startup
│   └── models.py           # Pydantic v2 models
├── config/
│   ├── conserved_regions.json
│   └── weights.json
├── dashboard/
│   └── app.py              # Streamlit UI
├── generation/
│   ├── interface.py        # GeneratorInterface Protocol
│   └── mock_generator.py   # MVP generator (replace with BioNeMo)
├── ranking/
│   └── weighted.py         # Weighted ranker
├── scoring/
│   ├── biological.py
│   ├── carbon.py
│   └── feasibility.py
├── tests/
│   └── conftest.py
├── requirements.txt
└── specs/001-enzyme-platform/   # Full design artifacts
```

For complete design documentation see [`specs/001-enzyme-platform/quickstart.md`](specs/001-enzyme-platform/quickstart.md).
