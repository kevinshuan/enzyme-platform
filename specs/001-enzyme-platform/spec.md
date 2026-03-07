# Feature Specification: AI-Designed Carbon-Reducing Enzyme Platform

**Feature Branch**: `001-enzyme-platform`
**Created**: 2026-02-24
**Status**: Draft

## Clarifications

### Session 2026-02-24

- Q: Are generation results stored server-side after the response is returned? → A: No persistence — stateless; results returned in response only.
- Q: Can researchers export results to a file from the dashboard? → A: CSV download — a button exports the full ranked candidate list as a `.csv` file.
- Q: Does the API require authentication or access control? → A: No authentication — API is open; access controlled by network/deployment (localhost only in MVP).
- Q: What is the tie-breaking rule when two candidates share the same final score? → A: Secondary sort by biological score descending.
- Q: Can researchers manage conserved positions through the dashboard? → A: No — file edit only; researchers edit `config/conserved_regions.json` directly.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Generate Ranked Mutation Candidates (Priority: P1)

A researcher inputs a base enzyme amino acid sequence, sets a mutation rate and candidate count,
and receives a ranked list of mutant variants. Each variant is scored across three dimensions
(biological viability, carbon impact potential, and commercial feasibility) and sorted from most
to least promising.

**Why this priority**: This is the core value proposition of the platform. Without the ability to
generate and rank candidates, no other feature has meaning. Every other user story builds on this
foundation.

**Independent Test**: Can be fully tested by submitting a valid amino acid sequence via the API
and verifying that a sorted list of candidates with three independent scores and a final weighted
score is returned. Delivers value as a standalone research screening tool.

**Acceptance Scenarios**:

1. **Given** a valid amino acid sequence of 50+ characters, **When** the researcher requests 100
   candidates at a 5% mutation rate, **Then** the system returns exactly 100 ranked candidates
   each with a biological score, carbon score, feasibility score, and final score — all between
   0 and 1 inclusive.
2. **Given** a submitted request, **When** results are returned, **Then** candidates are ordered
   from highest final score to lowest with no ties unexplained.
3. **Given** a sequence shorter than 50 characters, **When** a generation is requested, **Then**
   the system rejects the request with a clear error message explaining the minimum length.
4. **Given** a sequence containing invalid characters (non-amino acid letters), **When** submitted,
   **Then** the system rejects it with a specific error identifying the invalid characters.

---

### User Story 2 - Configure Scoring Weights (Priority: P2)

A researcher adjusts the relative importance of biological viability, carbon impact, and commercial
feasibility before generating candidates. The ranking reflects the custom priority mix, allowing
the researcher to optimise for different research objectives without rerunning the full pipeline.

**Why this priority**: Different research contexts have different objectives — a sustainability
focus needs higher carbon weight; a commercial pilot needs higher feasibility weight. Configurable
weights make the platform reusable across contexts.

**Independent Test**: Can be fully tested by submitting two requests with the same seed but
different weight configurations, then verifying the ranking order differs appropriately. No UI or
dashboard required.

**Acceptance Scenarios**:

1. **Given** a custom weight configuration (e.g., carbon impact = 0.7, bio = 0.2, feasibility =
   0.1), **When** candidates are generated, **Then** the final scores reflect those weights and
   a high-carbon, low-bio candidate ranks above a high-bio, low-carbon one.
2. **Given** weights that do not sum to 1.0, **When** the request is submitted, **Then** the
   system rejects it with a clear validation error explaining the constraint.
3. **Given** no weight configuration is provided, **When** a request is submitted, **Then** the
   system uses the default weights (bio = 0.3, carbon = 0.4, feasibility = 0.3) without error.

---

### User Story 3 - Reproduce an Experiment (Priority: P3)

A researcher provides a seed value along with their original input parameters and receives the
exact same set of candidates and scores they obtained in a previous run. This allows experiments
to be shared, validated, and compared across sessions.

**Why this priority**: Reproducibility is a baseline expectation in research tooling. Without it,
the platform cannot support scientific communication or result validation. It is independent of the
dashboard and scoring weight features.

**Independent Test**: Can be fully tested by running the same request twice with the same seed and
asserting that the candidate lists, mutation positions, and all scores are byte-identical between
runs.

**Acceptance Scenarios**:

1. **Given** the same base sequence, mutation rate, candidate count, weights, and seed, **When**
   the request is submitted a second time, **Then** the ranked candidate list is identical to the
   first response in every field.
2. **Given** different seeds but the same input, **When** two requests are submitted, **Then** the
   resulting candidate lists differ (with overwhelming probability).
3. **Given** any successful response, **When** inspected, **Then** it includes the seed value used
   so the user can reproduce the run.

---

### User Story 4 - Explore Results on a Dashboard (Priority: P4)

A researcher submits a sequence and configuration via an interactive web interface, views a score
distribution histogram, a scatter plot comparing carbon impact versus feasibility, and a table of
the top 10 ranked candidates — all without writing code or calling an API directly.

**Why this priority**: The dashboard lowers the barrier for non-technical researchers to explore
results. It is independently deliverable after the core API (User Stories 1–3) is functional.

**Independent Test**: Can be fully tested by launching the dashboard, submitting a sample sequence,
and verifying that all three visualisations render with correct data and that the top-10 table
matches the expected ranking from the API.

**Acceptance Scenarios**:

1. **Given** the dashboard is open, **When** a researcher enters a sequence, sets sliders for
   mutation rate and scoring weights, and clicks Generate, **Then** results appear within 10 seconds
   without page reload.
2. **Given** results are displayed, **When** the researcher views the score histogram, **Then** it
   shows the distribution of final scores across all generated candidates.
3. **Given** results are displayed, **When** the researcher views the scatter plot, **Then** it
   shows each candidate as a point with carbon impact on one axis and feasibility on the other.
4. **Given** results are displayed, **When** the researcher views the ranked table, **Then** the
   top 10 candidates are shown with all four scores visible.

---

### Edge Cases

- What happens when the mutation rate is set to zero? (System MUST return the unmodified
  base sequence as the only or repeated candidate, clearly labelled.)
- What happens when all mutable positions (non-conserved) are exhausted and no valid mutation
  can be made? (System MUST surface a clear error rather than silently returning an invalid candidate.)
- How does the system handle a request for 1000 candidates on a minimal-length (50-character)
  sequence with a high mutation rate? (Must not crash; may produce warnings about limited sequence diversity.)
- What happens when scoring weights sum to 0.9999 due to floating-point rounding? (System MUST
  accept values within a tolerance of ±0.001.)
- How are tied final scores handled in ranking? Primary sort: final score descending. Tie-break:
  biological score descending. Rule is documented in the API response schema.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST accept a base enzyme amino acid sequence and produce a ranked list of
  mutant candidates within a single request.
- **FR-002**: System MUST reject sequences shorter than 50 amino acid characters with a descriptive
  error message.
- **FR-003**: System MUST reject input sequences containing characters outside the standard 20
  amino acid alphabet (ACDEFGHIKLMNPQRSTVWY) and identify the offending characters.
- **FR-004**: System MUST score every generated candidate across three independent dimensions:
  biological viability, carbon impact potential, and commercial feasibility.
- **FR-005**: All three dimension scores and the final combined score MUST be values in the range
  [0.0, 1.0] for every candidate.
- **FR-006**: System MUST protect user-configured conserved positions from mutation during
  candidate generation.
- **FR-007**: System MUST limit mutation count per candidate to a configurable maximum threshold;
  candidates exceeding this threshold MUST be discarded and regenerated.
- **FR-008**: System MUST rank candidates in descending order by final weighted score. Ties MUST
  be broken by biological score descending. The tie-breaking rule MUST be documented in the API
  response schema.
- **FR-009**: System MUST allow users to configure scoring weights for each dimension; weights MUST
  sum to 1.0 (within ±0.001 tolerance).
- **FR-010**: System MUST apply default weights (biological 0.3, carbon 0.4, feasibility 0.3) when
  the user does not provide custom weights.
- **FR-011**: System MUST accept an optional seed value and produce identical candidate sets for
  identical seed + input combinations.
- **FR-012**: System MUST include the seed used in every response so the run can be reproduced.
- **FR-013**: System MUST emit structured log entries for each scoring stage, capturing candidate
  identifier, score values, and timestamp.
- **FR-014**: System MUST clearly label all outputs as simulation proxies — not biological
  predictions or wet-lab validated results — in API responses and the dashboard.
- **FR-015**: System MUST expose candidate generation and ranking via a programmatic request
  interface (API).
- **FR-016**: System MUST provide an interactive web dashboard for submitting requests and
  visualising results without writing code.
- **FR-017**: Dashboard MUST display: a score distribution histogram, a carbon-vs-feasibility
  scatter plot, and a ranked table of the top 10 candidates.
- **FR-018**: Dashboard MUST provide a "Download CSV" button that exports the full ranked
  candidate list (all candidates, all four scores, mutation positions) as a `.csv` file.

### Key Entities

- **Enzyme Candidate**: A mutated variant of the base sequence. Has a unique identifier, the
  original and mutated sequences, the list of changed positions, and four score values (biological,
  carbon, feasibility, final). Candidates are the primary unit of research output.
- **Scoring Weights**: A user-supplied or default configuration specifying the relative importance
  of each scoring dimension. Governs how the final score is computed. Must sum to 1.0.
- **Conservation Map**: A configuration listing amino acid positions that are biologically critical
  and MUST NOT be mutated. Loaded from `config/conserved_regions.json` at startup; shared across
  all runs. Managed by direct file edit only — no dashboard UI for this entity.
- **Generation Request**: A single invocation specifying the base sequence, mutation rate, candidate
  count, optional seed, and optional scoring weights. Produces one ranked result set.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A researcher can generate and view 100 ranked mutation candidates from a single
  sequence submission in under 10 seconds end-to-end.
- **SC-002**: The system generates 500 candidates and returns ranked results in under 3 seconds
  (excluding network overhead).
- **SC-003**: All candidate scores across all runs are confirmed to fall within [0.0, 1.0] — zero
  out-of-range values across a test set of 10,000 generated candidates.
- **SC-004**: Running the same generation request with the same seed twice produces byte-identical
  ranked results 100% of the time.
- **SC-005**: A researcher with no programming background can submit a request and interpret
  results using the dashboard without consulting documentation.
- **SC-006**: The system handles a peak request of 1,000 candidates without memory usage exceeding
  500 MB on the host machine.
- **SC-007**: The platform continues to produce correctly ranked results after the generation source
  is changed, with no modifications required to the scoring or result presentation components.

## Assumptions

- The platform is a single-user research tool in MVP phase; concurrent multi-user access and
  authentication are out of scope. The API requires no authentication and is expected to run
  on localhost or a private network only. No API key or session management is implemented in MVP.
- The system is stateless — generation results are NOT stored server-side. Results are returned
  in the API response only. Users who need to retain results must save them locally. The
  seed-based reproducibility (FR-011, FR-012) is the mechanism for re-running identical
  experiments.
- Conservation map is a static project-level configuration, not per-request user input. It is
  managed by editing `config/conserved_regions.json` directly; no dashboard interface is provided.
- The biological, carbon, and feasibility scores are proxy metrics; no claim of biological
  accuracy is made, and the platform is not designed to replace wet-lab validation.
- GPU acceleration is NOT required for the MVP; all proxy scoring runs on CPU. BioNeMo/GPU
  integration is a planned Phase 2 extension.
- The default mutation rate range (0.001–0.2) and candidate count range (1–1000) are fixed for
  MVP; they may become configurable in Phase 2.
