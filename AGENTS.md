# AGENTS.md

## Purpose
This file gives coding agents a reliable, project-specific operating guide for this repository.

## Project Snapshot
- **Project**: AI-Designed Carbon-Reducing Enzyme Platform — MVP
- **Stack**: FastAPI, Loguru, Pydantic v2, NumPy, Pandas, Plotly, Streamlit, Pytest, Ruff, Docker.
- **No database**: this is a stateless application. There is no SQLAlchemy, Alembic, or psycopg in the runtime stack.
- **App entrypoint**: `src/main.py`
- **Source root**: `src/` (commands rely on `PYTHONPATH=src` for imports like `from main import app` in tests).
- **Feature module**: `src/enzyme/` — all domain logic lives here.
- **Generator backend**: controlled by `GENERATOR_BACKEND` env var (`mock` default, `bionemo` for Phase 2).

## Repository Layout (Important Paths)
```
src/
├── main.py                      # FastAPI app, lifespan, CORS, router registration
├── config.py                    # GlobalSettings (GLOBAL_ prefix, pydantic-settings)
├── logging_config.py            # Loguru setup + shutdown hook
├── exceptions.py                # Shared exception types (placeholder)
├── models.py                    # Shared model base (placeholder — no DB)
├── pagination.py                # Shared pagination helpers (placeholder)
└── enzyme/                      # Enzyme feature module
    ├── __init__.py
    ├── config.py                # Loads config/conserved_regions.json + config/weights.json at startup
    ├── constants.py             # AMINO_ACIDS, VALID_AA
    ├── dependencies.py          # FastAPI DI helpers (conserved_positions, max_mutation_threshold)
    ├── exceptions.py            # EnzymeValidationError, GeneratorError
    ├── models.py                # EnzymeCandidate (internal domain model)
    ├── schemas.py               # Pydantic request/response schemas (API contract)
    ├── router.py                # APIRouter: POST /generate, GET /health
    ├── utils.py                 # validate_sequence helper
    └── service/
        ├── __init__.py
        ├── generator.py         # Mock candidate generator (swap for BioNeMo in Phase 2)
        ├── ranking.py           # rank_candidates — weighted sort with tie-breaking
        └── scoring/
            ├── __init__.py
            ├── biological.py    # BLOSUM62-based stability scorer
            ├── carbon.py        # CO₂ efficiency + charge neutrality scorer
            └── feasibility.py   # Manufacturability scorer (Cys/Trp fraction)

config/
├── conserved_regions.json       # 0-indexed positions that must not be mutated
└── weights.json                 # Default scoring weights + max_mutation_threshold

dashboard/
└── app.py                       # Streamlit dashboard (calls API via HTTP)

tests/
├── conftest.py                  # Shared fixtures (sequences, weights, rng)
├── test_main.py                 # API smoke test (GET /health)
└── unit/
    ├── test_biological.py       # BLOSUM62 scorer unit tests
    ├── test_carbon.py           # Carbon scorer unit tests
    └── test_feasibility.py      # Feasibility scorer unit tests
```

Other root-level files:
- `alembic.ini`: present as template artifact — not used (no DB).
- `pytest.ini`: pytest runtime configuration.
- `Makefile`: standard local commands.
- `scripts/new_feature.sh`: feature scaffold generator (`make new-feature`).
- `templates/feature_scaffold/`: source scaffold for new feature modules.

## Development Architecture
- One FastAPI app, split into feature modules under `src/`.
- `src/enzyme/` is the only feature module. Add new feature folders via `make new-feature name=<name>`.
- Shared/global concerns stay in `src/`; feature-owned concerns stay in `src/enzyme/`.
- Ownership rule: if logic is reused by multiple features or needed at bootstrap → `src/`; otherwise → `src/<feature>/`.

### Global Layer (`src/`)
- `main.py`: app creation, middleware, lifespan hooks, router registration.
- `config.py`: `GlobalSettings` with `GLOBAL_` env prefix. Currently only `generator_backend` field.
- `logging_config.py`: Loguru setup, file + stdout sinks, shutdown handler.

### Enzyme Feature Layer (`src/enzyme/`)
- `config.py`: loads `config/*.json` files once at import via `_EnzymeSettings`. No env prefix needed — config is file-based.
- `models.py`: `EnzymeCandidate` — internal mutable domain object (not exposed in API responses).
- `schemas.py`: `GenerateRequest`, `GenerateResponse`, `CandidateResponse`, `ScoringWeights`, `ResponseMeta` — the API contract.
- `router.py`: thin HTTP layer — validates input, wires service calls, maps to response schemas.
- `service/generator.py`: mock generator (BioNeMo swap point). Controlled by `GENERATOR_BACKEND` env var.
- `service/scoring/`: three independent, deterministic scorers (biological, carbon, feasibility).
- `service/ranking.py`: applies `ScoringWeights` and sorts by `final_score DESC`, `bio_score DESC` on tie.

## Scoring Pipeline (POST /generate)
```
validate_sequence()
  → generate_candidates()          # mock or bionemo backend
  → score_biological()             # BLOSUM62 stability
  → score_carbon(stability_score)  # CO₂ efficiency × stability − production_cost
  → score_feasibility()            # Cys/Trp manufacturability + mutation difficulty
  → rank_candidates()              # weighted sort
  → GenerateResponse
```
- Biological scorer runs first; its stability sub-score is passed to the carbon scorer to avoid redundant computation.
- All scorers output values clamped to [0.0, 1.0].
- Carbon and feasibility scorers are fully deterministic from sequence composition.

## BioNeMo Swap Point (Phase 2)
To replace the mock generator:
1. Create `src/enzyme/service/bionemo_generator.py` implementing `generate_candidates(...)` with the same signature as `generator.py`.
2. Set `GENERATOR_BACKEND=bionemo` in the environment.
3. No other files need to change.

## Implementation Patterns (Required)

### Config pattern
- Global settings: `src/config.py` via `pydantic-settings` (`GlobalSettings`, `GLOBAL_` prefix).
- Feature config: `src/enzyme/config.py` reads JSON files. Use `enzyme_settings` singleton in router/service code.
- Do not read `config/*.json` files directly in router or service code; always go through `enzyme_settings`.

### No-database pattern
- This app is stateless. Do not add SQLAlchemy, Alembic, or psycopg unless explicitly requested.
- `src/database.py` exists as a template artifact; do not import it in enzyme code.
- No `app.state` engine/sessionmaker wiring needed.

### Schema vs model separation
- `EnzymeCandidate` (`enzyme/models.py`): mutable internal object passed between generator, scorers, and ranker.
- API schemas (`enzyme/schemas.py`): immutable request/response contracts exposed via HTTP. Never use `EnzymeCandidate` directly in API responses.

### Router/service pattern
- Keep `router.py` thin: input validation, dependency resolution, response mapping.
- Keep business logic in `service/` — scoring, generation, ranking.
- Use `enzyme_settings` (not function arguments) for config values in the router.

### Logging pattern
- Use **Loguru** (`from loguru import logger`). Never use `logging.basicConfig` or `logging.getLogger`.
- Logging is configured in `src/logging_config.py`. Do not configure sinks in feature code.

## Feature Development Checklist
1. Create scaffold: `make new-feature name=<feature_name>`.
2. Define feature settings in `src/<feature>/config.py` if needed.
3. Add internal models in `src/<feature>/models.py`.
4. Add API schemas in `src/<feature>/schemas.py`.
5. Implement business logic in `src/<feature>/service.py` (or `service/` package).
6. Add endpoints in `src/<feature>/router.py`.
7. Register router in `src/main.py` via `app.include_router(...)`.
8. Add tests in `tests/` covering happy path and error paths.

## Dependency Management Policy (Required)
- Use `uv` as the only dependency/environment manager.
- Pin Python version: `uv python pin <version>`
- Create venv: `uv venv`
- Add runtime dep: `uv add <package>`
- Add dev dep: `uv add --dev <package>`
- Remove dep: `uv remove <package>`
- Sync from lockfile: `uv sync --frozen --no-cache`
- Runtime deps: `fastapi`, `uvicorn`, `pydantic`, `pydantic-settings`, `loguru`, `numpy`, `pandas`, `plotly`, `streamlit`, `requests`
- Dev-only deps: `pytest`, `pytest-asyncio`, `ruff`, `httpx`, `pytest-cov`
- Do not use `pip install`, `requirements.txt`, `poetry`, `pipenv`, or `conda`.

## Standard Commands
| Command | Action |
|---|---|
| `make install` | Sync deps from lockfile (`uv sync --frozen --no-cache`) |
| `make api` | Start FastAPI server on :8000 with auto-reload |
| `make dashboard` | Start Streamlit dashboard on :8501 |
| `make run` | Start FastAPI server (no explicit port) |
| `make test` | Full test suite with coverage |
| `make test-unit` | Unit tests only |
| `make test-integration` | Integration tests only |
| `make lint` | Ruff lint check |
| `make format` | Ruff format |
| `make new-feature name=<n>` | Scaffold a new feature module |
| `make up` / `make down` | Docker compose up/down |

## Testing Guidance
- Test runner: `pytest` via `make test`.
- Tests live under `tests/` using `test_*.py` naming.
- `pytest.ini` is the source of truth: `pythonpath = src`, `testpaths = tests`, `asyncio_mode = auto`.
- For API tests use `fastapi.testclient.TestClient`.
- Coverage target: ≥ 80% on touched scorer/service/router logic.
- Every endpoint change needs: status code assertion, happy-path response shape check, at least one error-path test.

## Linting and Formatting Policy (Required)
- Linter + formatter: **Ruff** (`make lint` / `make format`).
- Before any commit: run `make format`, `make lint`, `make test`.
- CI runs the same checks — keep local and CI behavior identical.

## CI/CD Defaults
- Default CI runner: `k8s`.
- CI pipeline: `.gitlab-ci.yml` runs `make lint` and `make test`.

## Environment and Config
- Local dev: one root `.env` file (copy from `.env.example`).
- `GLOBAL_` prefix for global settings (see `src/config.py`).
- `GENERATOR_BACKEND`: `mock` (default) or `bionemo`. Set in `.env` or as env var.
- For Kubernetes deployments, inject env vars via Secret/ConfigMap. Do not bake `.env` into images.

## Coding Conventions
- All imports must be compatible with `PYTHONPATH=src`.
- Use `from loguru import logger` — never `import logging`.
- Keep scorers deterministic: no RNG inside scoring functions.
- RNG is created once in the router and passed explicitly to `generate_candidates`.
- Feature code must not import from `src/database.py`.
- Routers must not contain scoring or generation logic — delegate to `service/`.

## Agent Workflow Expectations
- Read related files before editing. Keep changes minimal and focused.
- Run narrowest useful checks first, then `make test`, then `make lint`.
- Do not add DB/SQLAlchemy/Alembic unless the user explicitly requests it.
- Do not introduce `logging.basicConfig` or alternate logging frameworks.
