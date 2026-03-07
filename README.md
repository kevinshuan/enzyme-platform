# FastAPI Template

A clean and modular FastAPI project template designed for production-ready applications, inspired by https://github.com/zhanymkanov/fastapi-best-practices. This repo ships a micro-service style, feature/module-oriented layout with a shared global layer, plus Docker, GitLab CI, Alembic config, and a simple HTML template for quick UI demos.

## 📁 Project Structure

```
fastapi-template/
├── alembic.ini               # Alembic configuration (create alembic/ on init)
├── docker-compose.yml        # App + Postgres service definitions
├── Dockerfile                # Container build (uv + uvicorn)
├── Makefile                  # Local developer commands
├── scripts/
│   ├── bootstrap.sh          # Interactive project bootstrap helper
│   └── new_feature.sh        # Feature scaffold generator (`make new-feature`)
├── logging.ini               # Placeholder only (default runtime logging uses Loguru)
├── pytest.ini                # Pytest settings (pythonpath, markers, discovery)
├── src/                      # Application source (PYTHONPATH=src)
│   ├── main.py               # FastAPI app entrypoint + CORS + healthcheck
│   ├── config.py             # Global config settings (shared)
│   ├── database.py           # Shared async DB factory/base + DI session dependency
│   ├── exceptions.py         # Shared exception types (extend as needed)
│   ├── logging_config.py     # Loguru setup + shutdown hook
│   ├── models.py             # Shared model mixins/base entities
│   ├── pagination.py         # Shared pagination utilities (placeholder)
│   └── <feature_name>/       # Project-defined feature module(s)
│       ├── __init__.py       # Feature package marker
│       ├── config.py         # Feature-only configuration (prefix-based, shared env source)
│       ├── constants.py      # Feature constants
│       ├── dependencies.py   # Feature-specific dependencies
│       ├── exceptions.py     # Feature-specific exceptions
│       ├── models.py         # Feature models
│       ├── router.py         # APIRouter endpoints
│       ├── schemas.py        # Pydantic schemas
│       ├── service.py        # Or `service/` package + `__init__.py`
│       └── utils.py          # Feature utility helpers
├── templates/                # Jinja2 templates (HTML demo)
│   ├── feature_scaffold/     # Source scaffold copied by `make new-feature`
│   │   ├── __init__.py
│   │   ├── router.py
│   │   ├── schemas.py
│   │   ├── service.py
│   │   └── ...
│   └── index.html            # Placeholder UI demo page
├── tests/                    # Pytest test suite
│   └── test_main.py          # Basic health/root test
├── .env.example              # Environment variable template (placeholder)
├── .dockerignore             # Docker ignore rules
├── .gitignore                # Git ignore rules
├── .gitlab-ci.yml            # GitLab CI (lint + tests)
└── README.md                 # This file
```

Note: this template keeps `src/` clean by default. Create project feature folders with `make new-feature name=<feature_name>`, which copies `templates/feature_scaffold/` into `src/<feature_name>/`. Runtime logging is configured via `src/logging_config.py` (Loguru). Some files are scaffold placeholders for project-specific implementation (for example `.env.example` and migration files). Local development uses a single root `.env` file; feature settings use prefixes but read from the same shared environment source.

Dependency management in this template is **uv-only**. Do not use `requirements/*.txt` files.

## 🧱 Development Architecture

- This template follows a micro-service-style FastAPI architecture: one app, split into feature modules under `src/`.
- Create feature folders that match your project domains with `make new-feature name=<feature_name>`.
- Put cross-feature/app-wide concerns in global `src/`.
- Put feature-owned concerns in `src/<feature>/`.
- Rule of thumb:
  - Shared across 2+ features or needed at app bootstrap -> `src/`
  - Used by only one feature -> `src/<feature>/`

### Global layer (`src/`)
- `main.py`: app bootstrap, middleware, lifespan, and router registration.
- `config.py`: shared/global settings (`GlobalSettings`, `GLOBAL_` prefix).
- `database.py`: async SQLAlchemy engine/session factory/base and `get_session`.
- `models.py`: shared model mixins/base entities.
- `exceptions.py` and `pagination.py`: shared cross-feature utilities.
- `logging_config.py`: centralized Loguru configuration.

### Feature layer (`src/<feature>/`)
- `config.py`: feature-only settings and env prefix (for example `PAYMENTS_`), loaded from the same shared environment source as global settings.
- `models.py`: feature-owned database models.
- `schemas.py`: feature request/response/update schemas.
- `router.py`: HTTP contract layer for that feature.
- `service.py` or `service/`: business logic and database operations.
- `dependencies.py`: feature dependency wiring.
- `exceptions.py`, `constants.py`, `utils.py`: feature-local supporting modules.

### Development patterns
- Create new feature modules with `make new-feature name=<feature_name>`.
- Keep routers thin; put business logic in the feature service layer.
- Start with `service.py`; if feature complexity grows, split into a `service/` package.
- When using `service/`, include `service/__init__.py` and re-export the public service API for clean imports (for example: `from src.<feature>.service import ...`).
- Keep schema definitions in `schemas.py`; avoid ad hoc dict contracts in routers.
- Keep DB engine/sessionmaker creation centralized in `src/database.py`.
- Create DB resources in app lifespan when `GLOBAL_DATABASE_URL` is set, store them in `app.state`, and resolve sessions via DI (`Depends(get_session)`).
- For DB-backed services, perform a startup readiness query (for example `SELECT 1`) in app lifespan and dispose the engine on shutdown.
- Treat `pool_pre_ping` as connection checkout validation, not as an app startup readiness check.
- Keep shared config in `src/config.py`; keep feature-only config in feature `config.py`.
- Use one root `.env` file for local development and distinct env prefixes for each settings class.
- Register new feature routers in `src/main.py`.

## ⚙️ Project Setup

### Quick Start (Recommended)

1. Clone this template and enter the project directory.

```bash
git clone git@gitlab.cedarsdigital.io:factor-pm/fastapi_template.git temp-project
mv temp-project <your_new_project_name>
cd <your_new_project_name>
```

2. Ask your agent to initialize this cloned template as a new project (do not run the service yet).

### Start a New Project from This Template

#### 1. clone and create new repo
```bash
git clone git@gitlab.cedarsdigital.io:factor-pm/fastapi_template.git temp-project
mv temp-project <your_new_project_name>
cd <your_new_project_name>
rm -rf .git
```

#### 2. Initial New Project
```bash
git init
uv python pin <python_version_of_your_project>
uv init
uv venv
source .venv/bin/activate
```

#### 3. Initialize project dependencies
```bash
make init
```

#### 4. Create local environment file
```bash
cp .env.example .env
```

Update values in `.env` for your local environment.

#### 5. Add remote Repo & Push first commit
```
git remote add origin <your_git_remote_url>
git add .
git commit -m ":tada: initial commit for <your_new_project_name>"
git branch -M main
git push -u origin main
```

#### Optional: one-step bootstrap
If you prefer a guided setup, run the bootstrap script after cloning:

```bash
bash scripts/bootstrap.sh
```

The script will ask for project name, remote URL, Python version, and whether to run `make init` for dependencies. It also removes itself before the initial commit.
The script re-initializes git, pins Python, creates the virtual environment, can run `make init`, and creates `.env` from `.env.example` when missing.

## 🧪 Example Files

### Example `src/config.py`

The snippet below shows a typical global settings pattern using `pydantic-settings`. It defaults to the repository root `.env` file for local development, supports `ENV_FILE` override when needed, and prefixes environment variables with `GLOBAL_`.

```python
# src/config.py
import os
from pathlib import Path
from typing import ClassVar

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class GlobalSettings(BaseSettings):
    env_file_path: ClassVar[Path] = Path(
        os.getenv("ENV_FILE", str(Path(__file__).resolve().parents[1] / ".env"))
    ).expanduser()
    model_config = ConfigDict(
        env_prefix="GLOBAL_",
        env_file=str(env_file_path) if env_file_path.exists() else None,
    )
    database_url: str | None = None
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 30
    db_pool_recycle: int = 1800


# Instantiate
global_settings = GlobalSettings()
```

### Example `src/database.py`

The snippet below shows an async SQLAlchemy 2.0 setup using `psycopg` + `AsyncAdaptedQueuePool`, with SSL enabled for non-local environments (dev/uat/prod) and skipped for localhost. The engine/sessionmaker are created in lifespan and stored on `app.state`; request handlers use `Depends(get_session)`.

```python
# src/database.py
from fastapi import Request
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import AsyncAdaptedQueuePool


# SQLAlchemy 2.0 recommended base class
class Base(DeclarativeBase):
    pass

def _as_async_url(url: str) -> str:
    """Ensure psycopg driver and async format."""
    db_url = make_url(url)
    if (
        db_url.drivername.startswith("postgresql")
        and "+psycopg" not in db_url.drivername
    ):
        db_url = db_url.set(drivername="postgresql+psycopg")
    return db_url.render_as_string(hide_password=False)


def _is_local(db_url) -> bool:
    """Check local/dev hosts, including common Docker names."""
    host = db_url.host or ""
    return host in {"localhost", "127.0.0.1", "db", "postgres"}


def _has_explicit_ssl(db_url) -> bool:
    """Check if SSL parameters are already present."""
    return any(
        key in (db_url.query or {})
        for key in ("ssl", "sslmode", "sslrootcert", "sslcert", "sslkey")
    )


def create_engine_and_sessionmaker(
    url: str,
    *,
    pool_size: int,
    max_overflow: int,
    pool_timeout: int,
    pool_recycle: int,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    db_url = make_url(_as_async_url(url))

    if not _is_local(db_url) and not _has_explicit_ssl(db_url):
        query_params = dict(db_url.query)
        query_params["sslmode"] = "require"
        db_url = db_url.set(query=query_params)

    final_async_url = db_url.render_as_string(hide_password=False)
    connect_args = {"prepare_threshold": 0}
    pool_kwargs = {
        "poolclass": AsyncAdaptedQueuePool,
        "pool_size": pool_size,
        "max_overflow": max_overflow,
        "pool_timeout": pool_timeout,
        "pool_recycle": pool_recycle,
        "pool_pre_ping": True,
        "connect_args": connect_args,
    }
    engine = create_async_engine(final_async_url, **pool_kwargs)
    session_factory = async_sessionmaker(
        bind=engine, expire_on_commit=False, class_=AsyncSession
    )
    return engine, session_factory


def _require_sessionmaker(
    request: Request,
) -> async_sessionmaker[AsyncSession]:
    sessionmaker = getattr(request.app.state, "sessionmaker", None)
    if sessionmaker is None:
        raise RuntimeError("Database sessionmaker is not initialized.")
    return sessionmaker


async def get_session(request: Request):
    """FastAPI dependency: provide a DB session from app.state."""
    sessionmaker = _require_sessionmaker(request)
    async with sessionmaker() as db:
        yield db
```

### Example `src/models.py`

The snippet below shows a minimal SQLAlchemy 2.0 model using `Mapped` and `mapped_column`. It is meant as a simple example that teams can replace with their domain models.

```python
# src/models.py
from datetime import datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class ExampleModel(Base):
    __tablename__ = "example_models"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
```

## 🧰 Makefile Usage

### Default Makefile Usage

```bash
make init
make install
```

- `make init`: initialize baseline dependencies for a new project cloned from this template.
- `make install`: sync dependencies from lockfile (`uv sync --frozen --no-cache`).
- `make sync-dev`: sync dev dependency group.
- `make sync-prod`: sync runtime-only dependencies (no dev extras).

### Environment Dependency Management (UV)

- This template uses only two dependency scopes:
  - Runtime (production) dependencies.
  - Development dependencies (`--dev`) for tools like `pytest`, `ruff`, etc.
- How to choose scope:
  - Use runtime (`uv add`) if the package is needed by deployed/running app code in `src/`.
  - Use dev (`uv add --dev`) only for non-runtime tooling (tests, lint, notebooks, local scripts).
  - Do not choose `--dev` just because you are currently developing.
- Add dependencies:
  - Runtime: `uv add <package>`
  - Dev: `uv add --dev <package>`
- Remove dependencies:
  - Runtime: `uv remove <package>`
  - Dev: `uv remove --dev <package>`
- Sync dependencies:
  - Dev (default local): `uv sync --frozen --no-cache`
  - Runtime only: `uv sync --frozen --no-cache --no-dev`
- Examples:
  - Runtime: `fastapi`, `uvicorn`, `sqlalchemy`, `psycopg`, `pydantic-settings`, `loguru`, `alembic`
  - Dev-only: `pytest`, `ruff`, `ipykernel`, `httpx` (if only used in tests)
- Do not add or maintain `requirements/` files in this template.

### Create A New Feature Module

```bash
make new-feature name=users
```

- `make new-feature name=<feature_name>`: create `src/<feature_name>/` from `templates/feature_scaffold/`.

### Run App (Dev)

```bash
make run
```

### Run Tests

```bash
make test
```

- Test runner: `pytest`.
- Test files should be under `tests/` and follow `test_*.py`.
- High coverage is expected for new/changed code:
  - cover happy path, edge cases, and error paths
  - avoid shipping endpoint/business-logic changes without meaningful tests

### Pytest Configuration (`pytest.ini`)

- `pytest.ini` in repo root is the source of truth for test behavior.
- Current key settings:
  - `pythonpath = src`
  - `testpaths = tests`
  - naming: `python_files = test_*.py`, `python_classes = Test*`, `python_functions = test_*`
  - `asyncio_mode = auto`
  - `asyncio_default_fixture_loop_scope = function`
  - `markers`: `asyncio`
- Keep test locations/naming compatible with `pytest.ini`; avoid custom ad hoc discovery patterns.

### Migration (Alembic)

- Use Alembic for all database schema migrations.
- Alembic config file: `alembic.ini` (repo root).
- Typical migration flow:
  1. Update SQLAlchemy models.
  2. Generate revision: `uv run alembic revision --autogenerate -m "<message>"`
  3. Apply migration: `uv run alembic upgrade head`
  4. Roll back one revision if needed: `uv run alembic downgrade -1`
- If `alembic/` directory does not exist in a new project, initialize with:
  - `uv run alembic init alembic`
- Keep model changes and migration revision files in the same PR.

### Lint & Format

```bash
make lint     # check only
make format   # auto format
```

### Docker Commands

```bash
make up       # build and run docker-compose
make down     # stop containers
make rebuild  # rebuild containers from scratch
```

## 🔗 Notes

- `PYTHONPATH=src` is used for clean imports.
- Dockerfile is configured for Python 3.12 with [uv](https://github.com/astral-sh/uv) as the package manager.
- Alembic is installed for managing schema migrations (`alembic.ini`).
- For local development, declare environment variables in a single root `.env` file (copy from `.env.example`).
- App startup can run without `GLOBAL_DATABASE_URL` for non-DB routes.
- `GLOBAL_DATABASE_URL` must be set (via root `.env` or environment) for DB-backed routes/tests.
- Do not import global `engine` or `SessionLocal` in feature code; use `Depends(get_session)` for request-scoped DB access.
- Use `ENV_FILE` only when you need to load a non-default env file path.
- For deployments (for example Kubernetes), inject environment variables with platform config (Secret/ConfigMap); do not bake `.env` into images.
- GitLab CI runs `ruff` for linting/formatting and `pytest` for tests from `.gitlab-ci.yml`.

## 📝 Logging

- This template standardizes on **Loguru** for application logging.
- Central logging setup is implemented in `src/logging_config.py`.
- Runtime logs are written to `logs/app.log` and stdout by default.
- Keep logging configuration changes centralized in `src/logging_config.py`.
- `logging.ini` is a placeholder and is not the active runtime logging configuration in this template.

## ✅ Next Steps

- Create your first domain feature with `make new-feature name=<feature_name>`
- Write integration/unit tests in `tests/`
- Initialize an `alembic/` directory and wire models into migrations
- Implement routers, schemas, and services in your feature modules

---

Happy hacking! 🚀
