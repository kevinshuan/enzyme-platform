<!--
SYNC IMPACT REPORT
==================
Version change: [template/unpopulated] → 1.0.0
Bump rationale: MAJOR — first concrete ratification; all sections newly populated from template stubs.

Principles added (all new):
  - I.  Modular & Replaceable Architecture
  - II. Score Integrity
  - III. Simulation-First, BioNeMo-Ready
  - IV. Observability & Reproducibility
  - V.  Simplicity & YAGNI

Sections added (all new):
  - Technology Standards
  - Development Workflow & Quality Gates
  - Governance (populated)

Sections removed: N/A

Templates requiring updates:
  ✅ .specify/memory/constitution.md — updated (this file)
  ⚠  .specify/templates/plan-template.md — Constitution Check gates reference "gates determined based
     on constitution file"; these 5 principles are now the source of truth for those gates. No
     structural change required; content is resolved at plan-time by reading this file.
  ✅ .specify/templates/spec-template.md — no structural changes required; section ordering compatible.
  ✅ .specify/templates/tasks-template.md — no structural changes required; task categories align with
     modular architecture principle.
  ✅ .claude/commands/speckit.plan.md — reads this file at runtime; no outdated references found.
  ✅ .claude/commands/* — no CLAUDE-specific hardcoded references that conflict with generic guidance.
  ✅ .specify/templates/agent-file-template.md — update-agent-context.sh detects agent dynamically; no
     change required.

Deferred TODOs: None — all placeholders resolved.
-->

# GPU-Sequencing Constitution

> **Full project name**: AI-Designed Carbon-Reducing Enzyme Platform
> This is a simulation-based research product, not a validated wet-lab pipeline.

## Core Principles

### I. Modular & Replaceable Architecture

Every functional layer (generation, scoring, ranking, API, dashboard) MUST be implemented as an
independent module with a clearly defined input/output contract. The generation layer MUST be
abstracted behind an interface so the mock generator can be swapped for a real BioNeMo model
inference call without modifying scoring or ranking code. Modules MUST NOT share internal state
across layer boundaries.

**Rationale**: The MVP ships with a mock generator; Phase 2 integrates real BioNeMo. Coupling layers
together would make that migration costly and introduce regression risk across unrelated components.

### II. Score Integrity

All scores (biological, carbon impact, commercial feasibility) MUST satisfy these invariants:

- **Normalized**: Output MUST be in the range [0.0, 1.0] before being passed downstream.
- **Independent**: One scorer MUST NOT read or mutate another scorer's intermediate state.
- **Documented**: Every scoring formula MUST be defined as named variables with mathematical comments
  in source code and explained in `README.md`.
- **Configurable**: Scoring weights MUST be loaded from `config/weights.json`; hardcoded weight
  constants in production code paths are forbidden.
- **Auditable**: Each candidate's individual sub-scores MUST be preserved and returned alongside the
  final score in API responses.

**Rationale**: Multi-objective ranking is only meaningful when scores are comparable, independently
auditable, and not accidentally entangled.

### III. Simulation-First, BioNeMo-Ready

The MVP MUST use the mock sequence generator. All integration points with BioNeMo MUST be marked
with `# BioNeMo: replace with real inference` comments and placed behind a generator interface.
Production code and UI MUST NOT claim biological validity — all outputs are proxy metrics, not
wet-lab predictions. This caveat MUST appear in the dashboard and API documentation.

**Rationale**: BioNeMo API access may be unavailable during development. The platform MUST be
demonstrable without GPU/BioNeMo access, and the upgrade path MUST be a drop-in replacement, not
a rewrite.

### IV. Observability & Reproducibility

- Every scoring stage MUST emit structured log entries containing at minimum:
  `{candidate_id, stage, input_values, output_score, timestamp}`.
- A `seed` parameter MUST be accepted at the generation layer. Identical `seed` + identical input
  MUST produce byte-identical candidate lists.
- API responses MUST echo back the `seed` used so any result set is fully traceable and
  reproducible by consumers.

**Rationale**: Research tools require reproducibility. Structured logs allow debugging score
anomalies without re-running the full pipeline, and deterministic seeds enable comparison studies.

### V. Simplicity & YAGNI

No feature is built unless it is explicitly specified in the current milestone. Complexity MUST be
justified in writing before implementation. Weighted ranking MUST be delivered and validated before
Pareto frontier mode is attempted. Adding a new scoring dimension requires documented rationale.
Three clear functions are preferred over a premature abstraction.

**Rationale**: This is a side project with a solo or small team. Scope creep is the primary delivery
risk. Every unjustified abstraction is technical debt at this scale.

## Technology Standards

- **Language**: Python 3.11+
- **GPU / AI Framework**: BioNeMo (NVIDIA) + PyTorch; mock generation uses NumPy only
- **API layer**: FastAPI with Pydantic v2 for request/response validation
- **Scoring utilities**: NumPy, Pandas
- **Dashboard / UI**: Streamlit (MVP); React + Plotly is an optional Phase 2 upgrade
- **Visualization**: Plotly
- **Testing**: pytest; each scoring module MUST have unit tests covering boundary scores (0.0, 1.0),
  conserved-region violations, and empty mutation lists
- **Configuration**: JSON files in `config/` for conserved regions and scoring weights; no magic
  numbers in source files
- **GPU scope**: GPU acceleration is reserved for BioNeMo inference only; all proxy scoring runs
  on CPU. GPU resource usage MUST be logged when active.

## Development Workflow & Quality Gates

1. **MVP first**: Deliver the complete pipeline (generation → scoring → ranking → API → dashboard)
   with the mock generator before any Phase 2 extension begins.
2. **Independent testability**: Each module (`generation/`, `scoring/`, `ranking/`) MUST be
   runnable and testable in isolation without starting the full API server.
3. **Score normalization gate**: Every PR touching a scoring module MUST include or update a unit
   test that asserts output ∈ [0.0, 1.0] for valid inputs.
4. **No magic numbers**: All formula constants MUST be defined as named variables with inline
   comments explaining their domain meaning.
5. **Logging gate**: A scoring stage with no structured log output MUST NOT be merged to `main`.
6. **BioNeMo readiness gate**: Any change to the generation layer MUST confirm the mock ↔ BioNeMo
   interface contract (input/output schema) is preserved.
7. **Reproducibility gate**: The seed-controlled generation path MUST be covered by a test asserting
   deterministic output.

## Governance

This constitution supersedes all other development practices for GPU-Sequencing. It MUST be reviewed
whenever a new major component is added, a principle is violated, or BioNeMo is integrated in Phase 2.

**Amendment procedure**:
1. Propose the change in a PR description citing which principle is affected and why.
2. Update `CONSTITUTION_VERSION` following semantic versioning:
   - **MAJOR**: Principle removal, redefinition, or backward-incompatible governance change.
   - **MINOR**: New principle or section added, or materially expanded guidance.
   - **PATCH**: Clarifications, wording fixes, non-semantic refinements.
3. Set `LAST_AMENDED_DATE` to the merge date (ISO format YYYY-MM-DD).
4. Propagate changes to affected templates listed in the Sync Impact Report at the top of this file.

All PRs MUST include a brief "Constitution Check" note confirming no principles are violated, or
document justified exceptions in the plan's `Complexity Tracking` table.

**Version**: 1.0.0 | **Ratified**: 2026-02-24 | **Last Amended**: 2026-02-24
