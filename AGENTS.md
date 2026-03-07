# AGENTS.md

## Purpose
This file gives coding agents a reliable, project-specific operating guide for this repository.

## Project Snapshot
- Stack: FastAPI, SQLAlchemy (async), psycopg, Alembic, Loguru, Pytest, Ruff, Docker.
- App entrypoint: `src/main.py`
- Source root: `src/` (commands rely on `PYTHONPATH=src` for imports like `from main import app` in tests).
- Current state: this repo is a scaffold/template. Many module files are intentionally empty placeholders.

## Repository Layout (Important Paths)
- `src/main.py`: FastAPI app, lifespan hooks, CORS, root + health endpoints.
- `src/config.py`: global settings via `pydantic-settings` (`GlobalSettings`).
- `src/database.py`: async SQLAlchemy DB factory/session dependency (`app.state` lifecycle pattern).
- `src/logging_config.py`: Loguru setup + shutdown hook.
- `alembic.ini`: Alembic migration configuration (root-level).
- `pytest.ini`: pytest runtime configuration (root-level).
- `templates/feature_scaffold/`: source scaffold for new feature modules.
- `scripts/new_feature.sh`: feature scaffold generator (used by `make new-feature`).
- `tests/test_main.py`: baseline API smoke test.
- `Makefile`: standard local commands.
- `scripts/bootstrap.sh`: one-shot initializer for turning this template into a real project.

## Development Architecture (Micro-Service Style)
- This repository is a micro-service-style FastAPI app: one deployable app, split into feature modules under `src/`.
- This template keeps `src/` clean; no example feature folders are stored there by default.
- Create domain-specific feature folders under `src/` using `make new-feature name=<feature_name>`.
- Keep app-wide/shared concerns in `src/`; keep feature-owned concerns inside `src/<feature>/`.
- Ownership rule:
  - If logic/config is reused by multiple features or required by app bootstrap, place it in `src/`.
  - If logic/config is only for one feature, place it in `src/<feature>/`.

### Global Layer (`src/`)
- `src/main.py`: app creation, middleware, lifespan, and router registration.
- `src/config.py`: shared settings object(s), especially `GlobalSettings` with `GLOBAL_` env prefix.
- `src/database.py`: shared async DB factory/base and `get_session` dependency.
- `src/models.py`: shared model mixins/base entities used across features.
- `src/exceptions.py`: shared exception types for cross-feature usage.
- `src/pagination.py`: shared pagination helpers.
- `src/logging_config.py`: Loguru setup, sinks, and shutdown handling.

### Feature Layer (`src/<feature>/`)
- `config.py`: feature-only settings (`<FEATURE>_` env prefix recommended), loaded from the shared app environment source (root `.env` for local dev, injected env in deployments).
- `models.py`: feature-owned ORM models/tables.
- `schemas.py`: Pydantic request/response/update schemas for that feature.
- `router.py`: HTTP endpoints for that feature.
- `service.py` or `service/`: business logic and DB operations for that feature.
- `dependencies.py`: `Depends(...)` helpers scoped to feature concerns.
- `exceptions.py`: feature domain exceptions.
- `constants.py`: feature constants.
- `utils.py`: small feature-local utility functions.

## Feature Folder Contract
- Minimum required files for each feature:
  - `__init__.py`
  - `router.py`
  - `schemas.py`
  - `service.py` or `service/__init__.py`
- Common optional files (add when needed):
  - `config.py`
  - `models.py`
  - `dependencies.py`
  - `exceptions.py`
  - `constants.py`
  - `utils.py`
  - `.env.example` (documentation-only when feature-specific variables are needed; runtime still uses shared environment sources)

## Implementation Patterns (Required)
- Config pattern:
  - Keep global settings in `src/config.py` via `pydantic-settings`.
  - Keep feature-specific settings in `src/<feature>/config.py`; do not leak feature settings into global config.
  - For local development, use a single root `.env` file; avoid per-feature `.env` files.
  - Use `ENV_FILE` only when an alternate env file path is explicitly required.
  - Prefer importing settings objects over reading env vars ad hoc in routers/services.
- Database pattern:
  - Keep engine/sessionmaker factory logic centralized in `src/database.py`.
  - Keep SQLAlchemy usage async-first and reuse shared `Base` and `get_session`.
  - Create DB resources in `src/main.py` lifespan startup when `GLOBAL_DATABASE_URL` is set, store them on `app.state`, and resolve sessions through DI (`Depends(get_session)`).
  - Service startup without `GLOBAL_DATABASE_URL` is acceptable for non-DB routes; DB-backed routes/features still require DB config.
  - For DB-backed services, validate DB readiness in `src/main.py` lifespan startup and dispose the `app.state.engine` during lifespan shutdown.
  - `pool_pre_ping` improves pooled-connection health checks at checkout time; it does not replace startup readiness checks.
  - Do not create per-feature engines/sessionmakers unless explicitly requested.
- Model pattern:
  - Put shared/base model primitives in `src/models.py`.
  - Put domain tables in the owning feature's `models.py`.
  - Keep cross-feature model coupling explicit and minimal.
- Schema pattern:
  - Use feature-local schemas in `src/<feature>/schemas.py`.
  - Separate input/output/update schemas where appropriate.
  - Keep validation and serialization rules in schemas, not routers.
- Router/service pattern:
  - Keep `router.py` thin: request parsing, dependency wiring, response mapping.
  - Keep business rules and DB transaction logic in the feature service layer (`service.py` or `service/`).
  - Use `dependencies.py` for reusable DI objects (auth/session/context).
- Service modularization pattern:
  - Start with `service.py` for simple features.
  - If the feature becomes complex, replace/split into `service/` as a package.
  - In `service/`, add `__init__.py` and re-export the public service API for clean imports.
  - Routers and external callers should import from `src.<feature>.service` (package root), not deep service submodules.

## Feature Development Checklist
1. Create a new feature scaffold with `make new-feature name=<feature_name>`.
2. Define/update feature settings in `src/<feature>/config.py` (only if feature-specific).
3. Add/update models in `src/<feature>/models.py` (and shared model utilities in `src/models.py` only when truly cross-feature).
4. Add/update schemas in `src/<feature>/schemas.py`.
5. Implement business logic in `src/<feature>/service.py` (or `src/<feature>/service/` with `__init__.py` for complex features).
6. Add endpoints in `src/<feature>/router.py` and wire dependencies from `dependencies.py`.
7. Register router in `src/main.py`.
8. Add/adjust tests in `tests/` for happy path and error path behavior.

## Project Initialization (Agents)
Use this exact flow when initializing a newly cloned template project:
1. `rm -rf .git`
2. `git init`
3. `uv python pin <python version>`
4. `uv init`
5. `uv venv`
6. `make init`

- Before running any initialization step, if the user did not provide a Python version, ask which version they want to use and wait for their answer.
- During initialization-only requests, stop after `make init` unless the user explicitly asks to run app/tests.
- `make install` is for lockfile-based sync (`uv sync --frozen --no-cache`) after project metadata/lock are present.
- `scripts/bootstrap.sh` is intended for interactive human setup; agents should prefer the non-interactive flow above.

## Dependency Management Policy (Required)
- Use `uv` as the only dependency/environment manager for this repository.
- Pin project Python version with: `uv python pin <python version>`
- Create the project virtual environment with: `uv venv`
- Initialize baseline dependencies for a new project with: `make init`
- Install a package with: `uv add <package name>`
- Uninstall a package with: `uv remove <package name>`
- Fresh-start/sync dependencies with: `uv sync --frozen --no-cache`
- Use only two dependency scopes:
  - Runtime (production): `uv add <package>` / `uv remove <package>` / `uv sync --frozen --no-cache --no-dev`
  - Development: `uv add --dev <package>` / `uv remove --dev <package>` / `uv sync --frozen --no-cache`
- Classification rule for `--dev`:
  - Use runtime scope (`uv add`) when the package is required by the running service or imported by app code under `src/`.
  - Use dev scope (`uv add --dev`) only for non-runtime tooling (tests, lint/format, notebooks, local scripts).
  - Do not decide scope based on "I am developing now"; decide by whether production runtime needs the package.
- Examples:
  - Runtime: `fastapi`, `uvicorn`, `sqlalchemy`, `psycopg`, `pydantic-settings`, `loguru`, `alembic`
  - Dev-only: `pytest`, `pytest-asyncio`, `ruff`, `ipykernel`, `httpx` (when used only for tests)
- Do not use `pip install`, `requirements.txt` edits, `requirements/` folders, `poetry add`, `pipenv`, or `conda` workflows for dependency changes.

## Standard Commands
- Initialize baseline deps (new project): `make init`
- Create a feature scaffold: `make new-feature name=<feature_name>`
- Install deps: `make install`
- Sync dev deps: `make sync-dev`
- Sync prod deps: `make sync-prod`
- Run dev server: `make run`
- Run tests: `make test`
- Lint: `make lint`
- Format: `make format`
- Docker up/down: `make up` / `make down`

## Linting And Formatting Policy (Required)
- Linter: Ruff via `uv run ruff check .` (or `make lint`).
- Formatter: Ruff formatter via `uv run ruff format .` (or `make format`).
- Before opening/merging changes, run:
  - `make format`
  - `make lint`
  - `make test`
- Keep CI-compatible behavior: lint must pass with no errors and formatting must be clean (`uv run ruff format --check .` equivalent).

## CI/CD Defaults
- If a CI runner is not explicitly specified by the user/request, use `k8s` as the default runner.
- Keep lint/format/test checks in CI aligned with local commands (`make format`, `make lint`, `make test`).

## Coding Conventions for Agents
- Keep imports and execution compatible with `PYTHONPATH=src`.
- Preserve the module-oriented structure:
  - API layer in `router.py`
  - Business logic in `service.py` or `service/`
  - Validation contracts in `schemas.py`
  - DI helpers in `dependencies.py`
  - Domain errors/constants in `exceptions.py` and `constants.py`
- For request-driven DB access, use DI (`Depends(get_session)`); do not directly import global engine/session objects in feature code.
- Add new endpoints by wiring feature routers into `src/main.py` via `app.include_router(...)`.
- Keep placeholder files lightweight until functionality is required.
- Avoid adding unrelated refactors in the same change; prefer focused diffs.

## Testing Guidance
- Test runner: `pytest` (run via `make test`).
- Put tests under `tests/` using `test_*.py`.
- `pytest.ini` is the source of truth for test discovery/runtime behavior. Respect these settings:
  - `pythonpath = src`
  - `testpaths = tests`
  - naming: `test_*.py`, `Test*`, `test_*`
  - `asyncio_mode = auto`
  - `asyncio_default_fixture_loop_scope = function`
- For API tests, use `fastapi.testclient.TestClient` unless async behavior requires async clients/fixtures.
- High coverage is required for new/changed code.
- Coverage target: aim for >=90% coverage on touched feature/service/router logic and ensure critical paths are tested.
- Minimum bar for endpoint changes:
  - status code assertions
  - happy-path response shape/content checks
  - edge-case checks when applicable
  - at least one error-path test when applicable

## Environment & Config
- For local development, use one root `.env` file at the repository root (copy from `.env.example`).
- Settings are loaded from process environment variables; when present, the default env file path is the root `.env`.
- `ENV_FILE` can override the env file path when a custom location is required.
- Global settings use the `GLOBAL_` prefix (see `src/config.py`).
- Feature settings must use feature-specific prefixes (for example `USERS_`, `PAYMENTS_`) and read from the same shared environment source.
- `GLOBAL_DATABASE_URL` is required for DB-backed features.
- For deployments (for example Kubernetes), inject environment variables via platform configuration (Secret/ConfigMap); do not bake `.env` into images.
- `.env.example` files are placeholders; keep secrets out of git.

## Migration (Alembic)
- Use Alembic for all schema migrations.
- Migration config file is `alembic.ini` at repo root.
- Migration workflow:
  1. Update SQLAlchemy models (feature `models.py` and/or shared `src/models.py`).
  2. Generate migration: `uv run alembic revision --autogenerate -m "<message>"`
  3. Apply migration: `uv run alembic upgrade head`
  4. Roll back one revision (if needed): `uv run alembic downgrade -1`
- If the `alembic/` directory is missing in a new project, initialize it with `uv run alembic init alembic`.
- Keep model changes and migration revisions in the same change/PR.

## Logging
- Required: use **Loguru** for logging in this repository.
- Logging is configured in `src/logging_config.py`.
- Runtime logs are written to `logs/app.log` and stdout.
- Keep sink/format/rotation changes centralized in `src/logging_config.py`.
- Do not introduce `logging.basicConfig`, alternate logging frameworks, or `logging.ini`-based runtime config unless explicitly requested.
- Preserve the shutdown behavior (`shutdown_logging`) when adjusting app lifespan.

## Agent Workflow Expectations
- Before editing, quickly scan related files and keep changes minimal.
- If user asks to initialize a freshly cloned template, follow the `Project Initialization (Agents)` section.
- After edits, run the narrowest useful checks first, then broader checks:
  - targeted tests
  - `make test`
  - `make lint`
- If `make install` fails due to missing project metadata/lock (`pyproject.toml`, `uv.lock`), run the `Project Initialization (Agents)` flow first.
