# Data Model: AI-Designed Carbon-Reducing Enzyme Platform

**Branch**: `001-enzyme-platform` | **Date**: 2026-02-24

---

## Entities

### EnzymeCandidate

Primary unit of research output. Represents one mutated variant of the base sequence with all
associated scores.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | `str` | UUID v4, unique per generation run | Generated at creation |
| `base_sequence` | `str` | Length ≥ 50; chars ∈ `ACDEFGHIKLMNPQRSTVWY` | Original input sequence |
| `mutated_sequence` | `str` | Same length as `base_sequence` | Post-mutation sequence |
| `mutation_positions` | `list[int]` | 0-indexed; no conserved positions; no duplicates | Sorted ascending |
| `mutation_count` | `int` | = `len(mutation_positions)`; ≥ 1; ≤ `max_mutation_threshold` | Derived field |
| `bio_score` | `float` | [0.0, 1.0] | Set by `scoring/biological.py` |
| `carbon_score` | `float` | [0.0, 1.0] | Set by `scoring/carbon.py` |
| `feasibility_score` | `float` | [0.0, 1.0] | Set by `scoring/feasibility.py` |
| `final_score` | `float` | [0.0, 1.0] | Set by `ranking/weighted.py` |

**Identity**: `id` (UUID). Two candidates in the same run are never equal, even if their
mutated sequences happen to be identical (rare).

**Lifecycle**: Created by `generation/mock_generator.py` → scores assigned by scoring pipeline
→ `final_score` set by ranking engine → returned in API response. No persistence after response.

**Validation rules**:
- `mutated_sequence` MUST have same length as `base_sequence`
- `mutation_positions` MUST NOT contain any index present in `ConservationMap.positions`
- `mutation_count` MUST be ≥ 1 (zero-mutation candidates are discarded and regenerated)
- `mutation_count` MUST NOT exceed `max_mutation_threshold` from config

---

### ScoringWeights

User-supplied or default configuration controlling how the three dimension scores are combined
into a final score.

| Field | Type | Default | Constraints |
|-------|------|---------|-------------|
| `bio_weight` | `float` | 0.3 | ≥ 0.0 |
| `carbon_weight` | `float` | 0.4 | ≥ 0.0 |
| `feasibility_weight` | `float` | 0.3 | ≥ 0.0 |

**Validation rule**: `bio_weight + carbon_weight + feasibility_weight` MUST equal 1.0 within
±0.001 tolerance. Rejection with HTTP 422 if violated.

**Source**: Per-request (API body) or default from `config/weights.json`. Request value takes
precedence.

---

### ConservationMap

Positions in the amino acid sequence that are biologically critical and MUST NOT be mutated.
Shared across all generation runs in a session.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `positions` | `list[int]` | 0-indexed; unique; ≤ sequence length − 1 | Loaded at startup |

**Source**: `config/conserved_regions.json`. Managed by direct file edit only — no API or
dashboard interface. Loaded once at application startup; requires restart to take effect.

**File format**:
```json
{
  "conserved_positions": [5, 12, 18, 24, 31]
}
```

---

### GenerationRequest

Input to the `POST /generate` endpoint. Represents one generation invocation.

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `base_sequence` | `str` | Yes | Length ≥ 50; chars ∈ `ACDEFGHIKLMNPQRSTVWY` |
| `mutation_rate` | `float` | Yes | [0.001, 0.2] inclusive |
| `candidates` | `int` | Yes | [1, 1000] inclusive |
| `weights` | `ScoringWeights` | No | Defaults applied if omitted |
| `seed` | `int` | No | Any non-negative integer; `None` = non-deterministic |

---

### GenerationResponse

Output from `POST /generate`. Stateless — not stored server-side.

| Field | Type | Notes |
|-------|------|-------|
| `seed` | `int` | Echoed back (auto-generated if not supplied) |
| `total_generated` | `int` | Number of candidates in `ranked_candidates` |
| `weights_used` | `ScoringWeights` | Effective weights (default or user-supplied) |
| `ranked_candidates` | `list[CandidateResponse]` | Sorted by `final_score` desc, ties by `bio_score` desc |

---

### CandidateResponse

Serialised form of `EnzymeCandidate` returned in API responses. Subset of fields — full
sequence data included for downstream use.

| Field | Type | Notes |
|-------|------|-------|
| `id` | `str` | UUID |
| `mutated_sequence` | `str` | Full mutated amino acid sequence |
| `mutation_positions` | `list[int]` | 0-indexed positions |
| `mutation_count` | `int` | |
| `bio_score` | `float` | [0.0, 1.0] |
| `carbon_score` | `float` | [0.0, 1.0] |
| `feasibility_score` | `float` | [0.0, 1.0] |
| `final_score` | `float` | [0.0, 1.0] |

---

## Relationships

```
GenerationRequest ──(1:1)──> GenerationResponse
GenerationResponse ──(1:N)──> CandidateResponse   (N = candidates count)
GenerationRequest ──(uses)──> ScoringWeights       (supplied or default)
GenerationRequest ──(reads)──> ConservationMap     (loaded at startup)
CandidateResponse ──(is subset of)──> EnzymeCandidate
```

---

## Scoring Formula Reference

### Biological Score (`scoring/biological.py`)

```
HYDRO_SCALE = 9.0   # Kyte-Doolittle range: 4.5 − (−4.5)

stability_score    = 1.0 − (|mean_hydro(base) − mean_hydro(mutated)| / HYDRO_SCALE)
mutation_penalty   = mutation_count / len(base_sequence)
conserved_penalty  = mutations_in_conserved_positions / mutation_count

bio_score = 0.4 * stability_score
          + 0.4 * (1 − mutation_penalty)
          + 0.2 * (1 − conserved_penalty)
bio_score = clamp(bio_score, 0.0, 1.0)
```

### Carbon Impact Score (`scoring/carbon.py`)

```
efficiency_gain       = rng.uniform(0.9, 1.2)           # simulation proxy
normalized_efficiency = (efficiency_gain − 0.9) / 0.3   # → [0, 1]
deployment_factor     = stability_score                  # from bio scorer
production_cost_proxy = min(1.0, mutation_count * 0.01)

raw_carbon  = (normalized_efficiency * deployment_factor) − production_cost_proxy
carbon_score = (raw_carbon + 1.0) / 2.0                 # rescale [−1,1] → [0,1]
carbon_score = clamp(carbon_score, 0.0, 1.0)
```

### Feasibility Score (`scoring/feasibility.py`)

```
MAX_MUTATION_THRESHOLD = from config/weights.json

difficulty        = mutation_count / MAX_MUTATION_THRESHOLD  # → [0, 1]
manufacturability = stability_score                          # from bio scorer

feasibility_score = 0.5 * (1 − difficulty) + 0.5 * manufacturability
feasibility_score = clamp(feasibility_score, 0.0, 1.0)
```

### Final Score (`ranking/weighted.py`)

```
final_score = (bio_weight    * bio_score)
            + (carbon_weight * carbon_score)
            + (feasibility_weight * feasibility_score)

Sort: final_score DESC, then bio_score DESC (tie-break)
```
