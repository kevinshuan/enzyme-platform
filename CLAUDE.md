# GPU-sequencing Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-02-24

## Active Technologies

- **Language**: Python 3.11+
- **API**: FastAPI 0.115 + Pydantic v2 + Uvicorn 0.34
- **Dashboard**: Streamlit 1.42 + Plotly 5.24
- **Numerics**: NumPy ≥1.26,<2.0 (version-locked for RNG reproducibility), Pandas 2.2
- **HTTP client**: Requests 2.32 (Streamlit → FastAPI)
- **Testing**: pytest 8.3 + pytest-cov
- **Storage**: None (stateless — no database)

## Project Structure

```text
generation/       # Sequence generation modules (mock + BioNeMo interface)
scoring/          # Three independent scoring modules
ranking/          # Weighted ranking engine
app/              # FastAPI entry point, Pydantic models, route handlers
dashboard/        # Streamlit app
config/           # JSON config: conserved_regions.json, weights.json
tests/
├── conftest.py   # Session fixtures
├── unit/         # Per-module unit tests
└── integration/  # API end-to-end tests
```

## Commands

```bash
# Start API
uvicorn app.main:app --reload --port 8000

# Start Dashboard (separate terminal)
streamlit run dashboard/app.py

# Run tests with coverage
pytest --cov=. --cov-report=term-missing tests/

# Unit tests only
pytest tests/unit/

# Integration tests (requires API running)
pytest tests/integration/
```

## Code Style

- Python 3.11+: type hints on all public functions
- Pydantic v2: use `model_config = ConfigDict(...)`, `@field_validator`, `.model_dump()`
- NumPy RNG: always use `np.random.default_rng(seed)`, pass `Generator` as parameter
- All scoring constants: named variables with domain comments (no magic numbers)
- BioNeMo integration points: mark with `# BioNeMo: replace with real inference`

## Recent Changes

- 001-enzyme-platform: Initial platform — generation, scoring, ranking, FastAPI, Streamlit

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
