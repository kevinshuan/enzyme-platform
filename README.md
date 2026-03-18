# AI-Designed Carbon-Reducing Enzyme Platform

A modular FastAPI pipeline that generates mutated Carbonic Anhydrase-like enzyme candidates,
scores them across three dimensions, ranks them, and exposes results via a REST API
and interactive Streamlit dashboard.

> **Disclaimer**: All scores are simulation proxies. No wet-lab validation has been
> performed. This is an MVP mock generator designed for drop-in replacement with
> NVIDIA BioNeMo inference in Phase 2.

---

## 📁 Project Structure

```
enzyme-platform/
├── src/                              # Application source (PYTHONPATH=src)
│   ├── main.py                       # FastAPI app entrypoint + CORS + lifespan
│   ├── config.py                     # GlobalSettings (GLOBAL_ prefix, pydantic-settings)
│   ├── logging_config.py             # Loguru setup + shutdown hook
│   └── enzyme/                       # Enzyme feature module
│       ├── config.py                 # Loads config/*.json at startup
│       ├── constants.py              # AMINO_ACIDS, VALID_AA
│       ├── dependencies.py           # FastAPI DI helpers
│       ├── exceptions.py             # Feature exceptions
│       ├── models.py                 # EnzymeCandidate (internal domain model)
│       ├── schemas.py                # Pydantic request/response schemas
│       ├── router.py                 # APIRouter: POST /generate, GET /health
│       ├── utils.py                  # validate_sequence helper
│       └── service/
│           ├── generator.py          # Mock generator (swap for BioNeMo in Phase 2)
│           ├── ranking.py            # Weighted ranker with tie-breaking
│           └── scoring/
│               ├── biological.py     # BLOSUM62 stability scorer
│               ├── carbon.py         # CO₂ efficiency scorer
│               └── feasibility.py    # Manufacturability scorer
├── config/
│   ├── conserved_regions.json        # 0-indexed positions that must not be mutated
│   └── weights.json                  # Default scoring weights + max_mutation_threshold
├── dashboard/
│   └── app.py                        # Streamlit dashboard (calls API via HTTP)
├── tests/
│   ├── conftest.py                   # Shared fixtures
│   ├── test_main.py                  # API smoke test
│   └── unit/                         # Unit tests for all scorers
├── Makefile                          # Local developer commands
├── pyproject.toml                    # Project metadata + dependencies (uv)
├── pytest.ini                        # Pytest configuration
├── Dockerfile                        # Container build
├── docker-compose.yml                # App service definition
└── .env.example                      # Environment variable template
```

---

## ⚡ Quickstart

### 1 — Install dependencies

```bash
make install        # or: uv sync --frozen --no-cache
```

### 2 — Start the API (Terminal 1)

```bash
make api            # or: PYTHONPATH=src uv run python -m uvicorn src.main:app --port 8000 --reload
```

### 3 — Start the dashboard (Terminal 2)

```bash
make dashboard      # or: uv run python -m streamlit run dashboard/app.py
```

Open your browser at `http://localhost:8501`.

---

## 🌐 API Example

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

## ⚙️ Configuration

| File | Purpose |
|------|---------|
| `config/conserved_regions.json` | 0-indexed positions that must not be mutated |
| `config/weights.json` | Default scoring weights and `max_mutation_threshold` |

Edit these files to adjust defaults without touching code.

---

## 🧱 Architecture

```
POST /generate
  └── validate_sequence()
  └── np.random.default_rng(seed)      ← single RNG for full reproducibility
  └── generate_candidates()            ← service/generator.py  (swap for BioNeMo)
  └── score_biological()               ← BLOSUM62 substitution stability
  └── score_carbon(stability_score)    ← efficiency / deployment / cost proxy
  └── score_feasibility()              ← difficulty + manufacturability
  └── rank_candidates()                ← final_score DESC, bio_score DESC on tie
  └── GenerateResponse
```

**BioNeMo replacement (Phase 2)**: create `src/enzyme/service/bionemo_generator.py` with the same
`generate_candidates(...)` signature, then set `GENERATOR_BACKEND=bionemo`. No other files change.

---

## 📐 Scoring Formulas

### Biological (`service/scoring/biological.py`)
```
stability      = mean(normalize(BLOSUM62[base_aa][mut_aa]) for each mutation)
               = mean((BLOSUM62_score + 4) / 7)   -- [0, 1], 1.0 if no mutations
mutation_pen   = mutation_count / len(sequence)
conserved_pen  = mutations_in_conserved / mutation_count
bio_score      = 0.4·stability + 0.4·(1−mutation_pen) + 0.2·(1−conserved_pen)
```

### Carbon impact (`service/scoring/carbon.py`)
```
polar_fraction    = |polar_residues| / len(sequence)       # polar = {S,T,N,Q,D,E,K,R,H,Y}
charge_neutrality = max(0, 1 − |net_charge_per_residue| / 0.5)   # pH 7.4, CA optimum
co2_efficiency    = 0.5·polar_fraction + 0.5·charge_neutrality   # deterministic, [0,1]
production_cost   = min(1.0, mutation_count × 0.01)
raw               = co2_efficiency × stability − production_cost
carbon_score      = (raw + 1.0) / 2.0                     # rescale [−1,1] → [0,1]
```

### Commercial feasibility (`service/scoring/feasibility.py`)
```
challenging_frac = (Cys_count + Trp_count) / len(sequence)
manufacturability= max(0, 1 − challenging_frac / 0.20)    -- C/W expression burden [0,1]
difficulty       = mutation_count / max_mutation_threshold
feasibility_score= 0.5·(1−difficulty) + 0.5·manufacturability
```

---

## 🧰 Makefile Commands

| Command | Action |
|---|---|
| `make install` | Sync deps from lockfile |
| `make api` | Start FastAPI server on :8000 (auto-reload) |
| `make dashboard` | Start Streamlit dashboard on :8501 |
| `make test` | Full test suite with coverage |
| `make test-unit` | Unit tests only |
| `make test-integration` | Integration tests only |
| `make lint` | Ruff lint check |
| `make format` | Ruff auto-format |
| `make new-feature name=<n>` | Scaffold a new feature module under `src/` |
| `make up` / `make down` | Docker compose up / down |

---

## 🧪 Tests

```bash
make test
# or: PYTHONPATH=src uv run pytest --cov=. --cov-report=term-missing
```

Coverage target: ≥ 80%

---

## 🔗 Development Notes

- `PYTHONPATH=src` is required for clean imports (set automatically by all `make` commands).
- Dependency management is **uv-only**. Do not use `requirements.txt` or `pip install`.
- Logging uses **Loguru** (`from loguru import logger`). Do not use `logging.basicConfig`.
- This app is **stateless** — no database, no migrations.
- All scorers are deterministic from sequence composition; only the generator uses the seeded RNG.
- For local development, copy `.env.example` to `.env` and adjust as needed.
- `GENERATOR_BACKEND=bionemo` switches the generator from mock to BioNeMo (Phase 2).
