---

description: "Task list for AI-Designed Carbon-Reducing Enzyme Platform"
---

# Tasks: AI-Designed Carbon-Reducing Enzyme Platform

**Input**: Design documents from `specs/001-enzyme-platform/`
**Prerequisites**: plan.md ✅ | spec.md ✅ | data-model.md ✅ | contracts/api.md ✅ | research.md ✅

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no shared dependencies)
- **[Story]**: Which user story this task belongs to (US1–US4)
- All file paths are relative to repo root (`GPU-sequencing/`)

## Path Conventions

Single-project layout: `generation/`, `scoring/`, `ranking/`, `app/`, `dashboard/`, `config/`, `tests/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project skeleton, config files, and shared test fixtures.

- [X] T001 Create full directory structure: `generation/`, `scoring/`, `ranking/`, `app/`, `dashboard/`, `config/`, `tests/unit/`, `tests/integration/`
- [X] T002 Create `requirements.txt` with pinned versions: fastapi==0.115.0, uvicorn[standard]==0.34.0, pydantic==2.10.0, numpy>=1.26,<2.0, pandas==2.2.0, plotly==5.24.0, streamlit==1.42.0, requests==2.32.0, pytest==8.3.0, pytest-cov==6.0.0
- [X] T003 [P] Create `config/conserved_regions.json` with format `{"conserved_positions": [5, 12, 18, 24, 31]}` — placeholder values; replace with UniProt-sourced CA positions
- [X] T004 [P] Create `config/weights.json` with `{"bio_weight": 0.3, "carbon_weight": 0.4, "feasibility_weight": 0.3, "max_mutation_threshold": 20}`
- [X] T005 [P] Create `tests/conftest.py` with session-scoped fixtures: `test_sequence_minimal` (50-char valid AA string), `test_sequence_standard` (100-char), `test_conserved_positions` (list), `test_default_weights` (dict), `fixed_seed` (int = 42)
- [X] T006 [P] Add `__init__.py` to `generation/`, `scoring/`, `ranking/`, `app/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared Pydantic models and config loader that ALL modules depend on.

⚠️ **CRITICAL**: No user story work can begin until this phase is complete.

- [X] T007 Implement `app/models.py` with Pydantic v2 models: `ScoringWeights` (bio/carbon/feasibility floats, validator: sum ±0.001), `EnzymeCandidate` (id, base_sequence, mutated_sequence, mutation_positions, mutation_count, bio_score, carbon_score, feasibility_score, final_score — all floats Optional initially), `GenerateRequest` (base_sequence, mutation_rate 0.001–0.2, candidates 1–1000, weights Optional[ScoringWeights], seed Optional[int]), `CandidateResponse` (id, mutated_sequence, mutation_positions, mutation_count, four scores), `GenerateResponse` (seed, total_generated, weights_used, ranked_candidates, _meta with disclaimer and sort_order strings)
- [X] T008 [P] Implement `app/config_loader.py`: load `config/conserved_regions.json` → `list[int]` and `config/weights.json` → `ScoringWeights` + `max_mutation_threshold: int`; raise `RuntimeError` with clear message if files missing or malformed
- [X] T009 [P] Implement `generation/interface.py` defining `GeneratorInterface` as a `typing.Protocol` with method `generate(base_sequence, mutation_rate, n_candidates, conserved_positions, rng) -> list[EnzymeCandidate]`; add `# BioNeMo: replace with real inference` comment on method body

**Checkpoint**: Models, config loader, and generator interface ready — user story work can begin.

---

## Phase 3: User Story 1 — Generate Ranked Mutation Candidates (Priority: P1) 🎯 MVP

**Goal**: Full pipeline from sequence input → generation → scoring → ranking → API response.

**Independent Test**: `POST /generate` with a 50-char AA sequence returns 100 ranked candidates, each with four scores in [0,1], sorted by final_score desc (bio_score desc on tie), seed echoed in response, disclaimer present in `_meta`.

### Implementation for User Story 1

- [X] T010 [P] [US1] Implement `generation/mock_generator.py`: `generate_candidates(base_sequence, mutation_rate, n_candidates, conserved_positions, rng)` — for each candidate: copy sequence, iterate positions, apply `rng.random() < mutation_rate` gate, skip conserved positions, replace with `rng.choice(AMINO_ACIDS)` excluding original AA, record mutation_positions, enforce `mutation_count >= 1` (regenerate if 0), enforce `mutation_count <= max_mutation_threshold` (discard & regenerate), assign UUID v4 id, return `list[EnzymeCandidate]`; define `AMINO_ACIDS = list("ACDEFGHIKLMNPQRSTVWY")`
- [X] T011 [P] [US1] Implement `scoring/biological.py`: define `KYTE_DOOLITTLE = {'A': 1.8, 'C': 2.5, 'D': -3.5, 'E': -3.5, 'F': 2.8, 'G': -0.4, 'H': -3.2, 'I': 4.5, 'K': -3.9, 'L': 3.8, 'M': 1.9, 'N': -3.5, 'P': -1.6, 'Q': -3.5, 'R': -4.5, 'S': -0.8, 'T': -0.7, 'V': 4.2, 'W': -0.9, 'Y': -1.3}` and `HYDRO_SCALE = 9.0`; implement `compute_hydrophobicity(seq) -> float`; implement `score_biological(candidate, conserved_positions) -> float` using corrected formula: `stability = 1.0 - abs(hydro_orig - hydro_mut) / HYDRO_SCALE`, `mutation_penalty = mutation_count / len(base_sequence)`, `conserved_penalty = mutations_in_conserved / mutation_count`, `bio_score = 0.4*stability + 0.4*(1-mutation_penalty) + 0.2*(1-conserved_penalty)`; clamp to [0.0, 1.0]; emit structured log entry `{candidate_id, stage: "biological", input_values, output_score, timestamp}`
- [X] T012 [P] [US1] Implement `scoring/carbon.py`: implement `score_carbon(candidate, stability_score, rng) -> float` using: `efficiency_gain = rng.uniform(0.9, 1.2)`, `normalized_efficiency = (efficiency_gain - 0.9) / 0.3`, `deployment_factor = stability_score`, `production_cost = min(1.0, candidate.mutation_count * 0.01)`, `raw = normalized_efficiency * deployment_factor - production_cost`, `carbon_score = (raw + 1.0) / 2.0`; clamp to [0.0, 1.0]; emit structured log entry `{candidate_id, stage: "carbon", input_values, output_score, timestamp}`
- [X] T013 [P] [US1] Implement `scoring/feasibility.py`: implement `score_feasibility(candidate, stability_score, max_mutation_threshold) -> float` using: `difficulty = candidate.mutation_count / max_mutation_threshold`, `manufacturability = stability_score`, `feasibility_score = 0.5 * (1 - difficulty) + 0.5 * manufacturability`; clamp to [0.0, 1.0]; emit structured log entry `{candidate_id, stage: "feasibility", input_values, output_score, timestamp}`
- [X] T014 [US1] Implement `ranking/weighted.py`: implement `compute_final_score(candidate, weights) -> float` as weighted sum; implement `rank_candidates(candidates, weights) -> list[EnzymeCandidate]` sorting by `final_score DESC`, tie-break by `bio_score DESC`; emit log entry `{stage: "ranking", total_candidates, top_score, bottom_score, timestamp}`
- [X] T015 [US1] Implement `app/api.py`: `POST /generate` handler — validate request (sequence length ≥ 50, valid AA chars only, weights sum ±0.001); create `rng = np.random.default_rng(seed or auto-generate seed)`; load conserved positions; call mock generator; run scoring pipeline (biological → carbon → feasibility → final); call ranker; build `GenerateResponse` with seed echoed, `_meta.disclaimer`, `_meta.sort_order`; log request metadata at start; return response. `GET /health` returns `{"status": "ok", "version": "1.0.0"}`
- [X] T016 [US1] Implement `app/main.py`: create FastAPI app; register router from `api.py`; load `ConservationMap` and default `ScoringWeights` at startup via `config_loader.py`; add startup log confirming config loaded successfully

**Checkpoint**: `POST /generate` returns fully scored, ranked candidates. US1 independently testable via `curl` or API client.

---

## Phase 4: User Story 2 — Configure Scoring Weights (Priority: P2)

**Goal**: Per-request weight configuration overrides defaults; invalid weights rejected with clear error.

**Independent Test**: Submit two identical requests (same seed) with different weight configs; assert ranking order differs. Submit weights summing to 0.85; assert HTTP 422 with clear validation message.

### Implementation for User Story 2

- [X] T017 [US2] Add weight validation to `app/models.py` `ScoringWeights`: add `@model_validator(mode="after")` that checks `abs(bio_weight + carbon_weight + feasibility_weight - 1.0) <= 0.001`; raise `ValueError("weights must sum to 1.0 (got {sum}, tolerance ±0.001)")` if violated
- [X] T018 [US2] Update `app/api.py` `POST /generate` handler: when `request.weights` is provided, use it in place of default weights loaded from config; log `weights_source: "user"` or `"default"` in request metadata log entry
- [X] T019 [US2] Update `app/models.py` `GenerateResponse`: populate `weights_used` field with the effective `ScoringWeights` applied, whether user-supplied or default

**Checkpoint**: Custom weights applied to ranking; default weights used when omitted; invalid weights return HTTP 422. US2 independently testable without dashboard.

---

## Phase 5: User Story 3 — Reproduce an Experiment (Priority: P3)

**Goal**: Same seed + inputs → byte-identical ranked results every time; seed echoed in response.

**Independent Test**: Call `POST /generate` twice with identical body including `"seed": 42`; assert every field in `ranked_candidates` is identical between both responses including all scores, mutation_positions, and ids.

### Implementation for User Story 3

- [X] T020 [US3] Update `app/api.py`: when `request.seed` is `None`, generate a random seed via `int(np.random.default_rng().integers(0, 2**31))` and store it; always pass this seed to `np.random.default_rng(seed)` so it is deterministic; include the final seed in `GenerateResponse.seed`
- [X] T021 [US3] Update `generation/mock_generator.py`: ensure `rng` object is passed through to `scoring/carbon.py` (carbon score uses `rng.uniform`) so that the full pipeline is deterministic from a single seed — the same `rng` instance used for generation MUST be used for carbon scoring to guarantee byte-identical output
- [X] T022 [US3] Update `app/api.py` request log entry to include `{"seed_source": "user" | "auto-generated", "seed": <value>}` for traceability

**Checkpoint**: Same seed → byte-identical response. Different seeds → different results. Seed always present in response. US3 independently testable via two identical API calls.

---

## Phase 6: User Story 4 — Explore Results on a Dashboard (Priority: P4)

**Goal**: Streamlit web UI — form submission, 3 Plotly visualisations, top-10 table, CSV download.

**Independent Test**: Launch dashboard (`streamlit run dashboard/app.py`); submit sample sequence; assert histogram, scatter plot, and table render with data; download CSV and verify it contains all candidates with four scores.

### Implementation for User Story 4

- [X] T023 [US4] Implement `dashboard/app.py` form section: `st.set_page_config(layout="wide")`; sequence text area; `mutation_rate` slider (0.001–0.2, default 0.05, step 0.001); `candidates` number input (1–1000, default 100); weight sliders for bio/carbon/feasibility (each 0.0–1.0, default per config); "Generate" button; show `st.warning("⚠ Scores are simulation proxies — not biological predictions")` prominently
- [X] T024 [US4] Implement `dashboard/app.py` API call: on button click, POST to `http://localhost:8000/generate` via `requests`; show `st.spinner("Generating…")`; handle `ConnectionError` with `st.error("API not running — start with: uvicorn app.main:app --port 8000")`; handle HTTP 422 with `st.error(response.json()["detail"])`; store result in `st.session_state`
- [X] T025 [P] [US4] Implement `dashboard/app.py` score distribution histogram: using Plotly `go.Histogram` on `final_score` values across all candidates; x-axis label "Final Score", title "Score Distribution"; render with `st.plotly_chart`
- [X] T026 [P] [US4] Implement `dashboard/app.py` carbon-vs-feasibility scatter plot: using Plotly `go.Scatter` with `carbon_score` on x-axis, `feasibility_score` on y-axis, marker colour mapped to `final_score`, hover showing `id` and all four scores; render with `st.plotly_chart`
- [X] T027 [P] [US4] Implement `dashboard/app.py` top-10 ranked table: build `pd.DataFrame` from top 10 `ranked_candidates`; display columns: rank, id (truncated), mutation_count, bio_score, carbon_score, feasibility_score, final_score; render with `st.dataframe`
- [X] T028 [US4] Implement `dashboard/app.py` CSV download: build `pd.DataFrame` from ALL `ranked_candidates` (not just top 10) with columns: id, mutated_sequence, mutation_positions, mutation_count, bio_score, carbon_score, feasibility_score, final_score; convert to CSV string; render `st.download_button("Download CSV", csv_string, "candidates.csv", "text/csv")`

**Checkpoint**: All three visualisations render from a single form submission. CSV download includes all candidates. US4 independently testable by launching dashboard alone (requires API running).

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Input validation hardening, logging consistency, README, and quickstart validation.

- [X] T029 [P] Add sequence validation helper in `app/api.py`: extract inline validation into `validate_sequence(seq: str) -> None` raising `HTTPException(422)` with message listing invalid characters (e.g. `"Invalid characters: ['B', 'X']"`) and minimum length error separately
- [X] T030 [P] Add edge-case handling in `generation/mock_generator.py`: if `mutation_rate == 0.0`, return `n_candidates` copies of `EnzymeCandidate` with `mutated_sequence == base_sequence` and `mutation_count == 0`, labelled in log as `"zero_rate"`; if all non-conserved positions exhausted after 100 retries, raise `ValueError("Cannot generate mutations: all positions are conserved or sequence too short")`
- [X] T031 [P] Verify all scoring modules clamp output: add `assert 0.0 <= score <= 1.0` guard before returning in `biological.py`, `carbon.py`, `feasibility.py`; raise `RuntimeError(f"Score out of range: {score}")` if violated (catches formula regressions)
- [X] T032 [P] Create `README.md` at repo root: project description (with proxy disclaimer), quickstart commands (two terminals), config section, API example with `curl`, link to `specs/001-enzyme-platform/quickstart.md`
- [X] T033 Run quickstart validation per `specs/001-enzyme-platform/quickstart.md`: install deps → start API → start dashboard → `curl POST /generate` → confirm ranked response → confirm seed reproducibility → confirm CSV download

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately; T003–T006 parallelisable
- **Foundational (Phase 2)**: Requires Phase 1 complete — T007 first (models), then T008/T009 in parallel
- **US1 (Phase 3)**: Requires Phase 2 — T010–T013 parallelisable, T014 after T010–T013, T015 after T014, T016 after T015
- **US2 (Phase 4)**: Requires Phase 3 (US1 API running) — T017 → T018 → T019 sequential
- **US3 (Phase 5)**: Requires Phase 3 — T020 → T021 → T022 sequential
- **US4 (Phase 6)**: Requires Phase 3 — T023 → T024, then T025/T026/T027 parallel, T028 after T027
- **Polish (Phase 7)**: Requires all user stories complete — T029–T032 parallelisable, T033 last

### User Story Dependencies

- **US1 (P1)**: Depends on Foundational only — no other story dependency
- **US2 (P2)**: Depends on US1 (reuses API + models)
- **US3 (P3)**: Depends on US1 (reuses API + generator)
- **US4 (P4)**: Depends on US1 (calls API via HTTP) — independent of US2/US3

### Within Each User Story

- Models before services — services before route handlers — handlers before app entry point
- Each story complete and independently testable before moving to next

---

## Parallel Opportunities

### Phase 1 Parallel Launch (after T001, T002)
```
T003 config/conserved_regions.json
T004 config/weights.json
T005 tests/conftest.py
T006 __init__.py files
```

### Phase 2 Parallel Launch (after T007)
```
T008 app/config_loader.py
T009 generation/interface.py
```

### Phase 3 Parallel Launch (after T009)
```
T010 generation/mock_generator.py
T011 scoring/biological.py
T012 scoring/carbon.py
T013 scoring/feasibility.py
```

### Phase 6 Parallel Launch (after T024)
```
T025 dashboard histogram
T026 dashboard scatter plot
T027 dashboard top-10 table
```

### Phase 7 Parallel Launch
```
T029 sequence validation helper
T030 edge-case handling
T031 score clamp guards
T032 README.md
```

---

## Implementation Strategy

### MVP First (US1 Only — Phases 1–3)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (models + config loader + generator interface)
3. Complete Phase 3: US1 (mock generator + all 3 scorers + ranker + API)
4. **STOP and VALIDATE**: `curl POST /generate` → ranked candidates → all scores in [0,1] → disclaimer present
5. Demo-ready: full pipeline functional without dashboard

### Incremental Delivery

1. Phases 1–3 → US1 complete → API working (**MVP**)
2. Phase 4 → US2 complete → custom weights working
3. Phase 5 → US3 complete → seed reproducibility working
4. Phase 6 → US4 complete → dashboard + CSV export working
5. Phase 7 → Polish complete → production-ready

---

## Notes

- `[P]` tasks operate on different files — safe to run in parallel
- `[Story]` label maps each task to its user story for traceability
- Scoring modules (T010–T013) are fully independent — implement in any order or in parallel
- US2 and US3 are API-only — no dashboard work required for those stories
- US4 depends on a running API (`localhost:8000`) — start API before testing dashboard
- All scores MUST be clamped [0.0, 1.0] at source — never rely on downstream clamping
- NumPy `>=1.26,<2.0` MUST be pinned — do not upgrade without re-validating seed reproducibility
