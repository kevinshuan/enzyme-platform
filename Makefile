.PHONY: init new-feature install sync-dev sync-prod api dashboard run test test-unit test-integration lint format clean tidy up down rebuild

init:
	uv add fastapi "uvicorn[standard]" pydantic pydantic-settings loguru numpy pandas plotly streamlit requests
	uv add --dev ruff pytest pytest-asyncio httpx pytest-cov

new-feature:
	@if [ -z "$(name)" ]; then echo "Usage: make new-feature name=<feature_name>"; exit 1; fi
	bash scripts/new_feature.sh "$(name)"

install:
	uv sync --frozen --no-cache

sync-dev:
	uv sync --frozen --no-cache

sync-prod:
	uv sync --frozen --no-cache --no-dev

api:
	PYTHONPATH=src uv run uvicorn main:app --port 8000 --reload

dashboard:
	uv run streamlit run dashboard/app.py

run:
	PYTHONPATH=src uv run uvicorn main:app --reload

test:
	PYTHONPATH=src uv run pytest --cov=. --cov-report=term-missing

test-unit:
	PYTHONPATH=src uv run pytest tests/unit/

test-integration:
	PYTHONPATH=src uv run pytest tests/integration/

lint:
	uv run ruff check .

format:
	uv run ruff format .

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .venv

tidy:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true

up:
	docker-compose up --build

down:
	docker-compose down

rebuild:
	docker-compose down -v
	docker-compose up --build
