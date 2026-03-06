.PHONY: help install api dashboard test test-unit test-integration lint

help:
	@echo "Available commands:"
	@echo "  make install          Install dependencies (dev group included)"
	@echo "  make api              Start FastAPI server on :8000 with auto-reload"
	@echo "  make dashboard        Start Streamlit dashboard on :8501"
	@echo "  make test             Run full test suite with coverage"
	@echo "  make test-unit        Run unit tests only"
	@echo "  make test-integration Run integration tests only (requires API running)"

install:
	uv sync --group dev

api:
	uv run uvicorn app.main:app --port 8000 --reload

dashboard:
	uv run streamlit run dashboard/app.py

test:
	uv run pytest --cov=. --cov-report=term-missing tests/

test-unit:
	uv run pytest tests/unit/

test-integration:
	uv run pytest tests/integration/
