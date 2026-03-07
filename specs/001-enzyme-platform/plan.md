# Implementation Plan: AI-Designed Carbon-Reducing Enzyme Platform

**Branch**: `001-enzyme-platform` | **Date**: 2026-02-24 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/001-enzyme-platform/spec.md`

---

## Summary

Build a modular, stateless pipeline that generates Carbonic Anhydrase-like enzyme mutation
candidates, scores them across three independent dimensions (biological viability, carbon impact,
commercial feasibility), ranks them by a configurable weighted combination, and exposes the
results via a FastAPI REST endpoint and a Streamlit dashboard. The MVP uses a mock sequence
generator abstracted behind an interface for future BioNeMo replacement.

---

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: FastAPI 0.115, Pydantic v2, Streamlit 1.42, NumPy ≥1.26 <2.0 (pinned
for RNG reproducibility), Pandas 2.2, Plotly 5.24, Requests 2.32, Uvicorn 0.34
**Storage**: N/A — stateless; no database or file persistence of results
**Testing**: pytest 8.3 + pytest-cov; 80% coverage target
**Target Platform**: Local workstation (localhost); macOS/Linux/Windows compatible
**Project Type**: Web service (FastAPI) + dashboard (Streamlit); single-process each
**Performance Goals**: 500 candidates ranked in < 3 s; 100 candidates end-to-end in < 10 s
**Constraints**: CPU-only for MVP (no GPU); stateless; < 500 MB memory at 1000 candidates;
NumPy version pinned for RNG byte-identical reproducibility
**Scale/Scope**: Single user; 1–1000 candidates per request; localhost only

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Pre-Design | Post-Design | Notes |
|-----------|-----------|-------------|-------|
| I. Modular & Replaceable | ✅ PASS | ✅ PASS | generation/, scoring/, ranking/, app/, dashboard/ are independent modules; GeneratorInterface Protocol enables BioNeMo swap |
| II. Score Integrity | ✅ PASS | ✅ PASS | All scores clamped [0,1]; weights from config/weights.json; hydrophobicity formula corrected (÷9.0); sub-scores returned in response |
| III. Simulation-First, BioNeMo-Ready | ✅ PASS | ✅ PASS | mock_generator.py is MVP; interface.py defines swap contract; proxy disclaimer in API response and dashboard |
| IV. Observability & Reproducibility | ✅ PASS | ✅ PASS | Structured logs per scoring stage; seed parameter with default_rng; seed echoed in response |
| V. Simplicity & YAGNI | ✅ PASS | ✅ PASS | Weighted ranking only (no Pareto); two terminals for dev (no orchestrator); HTTP calls (no shared-state coupling) |

**No violations. No Complexity Tracking entries required.**

---

## Project Structure

### Documentation (this feature)

```text
specs/001-enzyme-platform/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── api.md           # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks — not created here)
```

### Source Code (repository root)

```text
GPU-sequencing/
├── generation/
│   ├── __init__.py
│   ├── interface.py          # GeneratorInterface Protocol (BioNeMo contract)
│   └── mock_generator.py     # Mock implementation (MVP)
├── scoring/
│   ├── __init__.py
│   ├── biological.py         # Kyte-Doolittle stability + mutation/conserved penalties
│   ├── carbon.py             # Carbon impact proxy scoring
│   └── feasibility.py        # Commercial feasibility scoring
├── ranking/
│   ├── __init__.py
│   └── weighted.py           # Weighted sum + bio_score tie-break
├── app/
│   ├── __init__.py
│   ├── main.py               # FastAPI app, startup config loader
│   ├── models.py             # Pydantic v2: GenerateRequest, GenerateResponse,
│   │                         #   CandidateResponse, ScoringWeights
│   └── api.py                # Route handlers (POST /generate, GET /health)
├── dashboard/
│   └── app.py                # Streamlit: form + 3 charts + CSV download
├── config/
│   ├── conserved_regions.json  # Static conserved positions (file-edit only)
│   └── weights.json            # Default weights + max_mutation_threshold
└── tests/
    ├── conftest.py             # Session fixtures: sequences, conserved map, rng
    ├── unit/
    │   ├── test_generator.py   # Mutation logic, seed reproducibility, edge cases
    │   ├── test_biological.py  # Bio score normalization, boundary conditions
    │   ├── test_carbon.py      # Carbon score normalization, boundary conditions
    │   ├── test_feasibility.py # Feasibility normalization, boundary conditions
    │   └── test_ranking.py     # Weight application, tie-breaking, sort order
    └── integration/
        └── test_api.py         # POST /generate end-to-end, validation errors, health
```

**Structure Decision**: Single-project layout (Option 1) with a top-level split between the
backend modules (`generation/`, `scoring/`, `ranking/`, `app/`) and the `dashboard/` Streamlit
app. Streamlit communicates with FastAPI via HTTP (not direct import) to preserve independent
testability per Constitution Principle I.

---

## Complexity Tracking

> No violations — table omitted per template instructions.
