# API Contract: AI-Designed Carbon-Reducing Enzyme Platform

**Branch**: `001-enzyme-platform` | **Date**: 2026-02-24
**Base URL**: `http://localhost:8000`
**Framework**: FastAPI + Pydantic v2
**Auth**: None (localhost only in MVP)

---

## Endpoints

### POST /generate

Generate, score, and rank enzyme mutation candidates.

**Request**

```
POST /generate
Content-Type: application/json
```

```json
{
  "base_sequence": "MKTIIALSYIFCLVFADYKDDDKGSGYQSGDYHKSYNKSVEYAKHHK",
  "mutation_rate": 0.05,
  "candidates": 100,
  "weights": {
    "bio_weight": 0.3,
    "carbon_weight": 0.4,
    "feasibility_weight": 0.3
  },
  "seed": 42
}
```

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `base_sequence` | string | Yes | Length ≥ 50; only chars `ACDEFGHIKLMNPQRSTVWY` |
| `mutation_rate` | float | Yes | 0.001 ≤ value ≤ 0.2 |
| `candidates` | integer | Yes | 1 ≤ value ≤ 1000 |
| `weights` | object | No | Omit to use defaults (bio=0.3, carbon=0.4, feasibility=0.3) |
| `weights.bio_weight` | float | No | ≥ 0.0 |
| `weights.carbon_weight` | float | No | ≥ 0.0 |
| `weights.feasibility_weight` | float | No | ≥ 0.0 |
| `weights` (sum) | — | — | Must sum to 1.0 ± 0.001 |
| `seed` | integer | No | Any non-negative integer; omit for non-deterministic run |

**Response 200 OK**

```json
{
  "seed": 42,
  "total_generated": 100,
  "weights_used": {
    "bio_weight": 0.3,
    "carbon_weight": 0.4,
    "feasibility_weight": 0.3
  },
  "ranked_candidates": [
    {
      "id": "3f2504e0-4f89-11d3-9a0c-0305e82c3301",
      "mutated_sequence": "MKTIIALSYIFCLVFADYKDDDKGSGYQSGDYHKSYNKSVEYAKHHK",
      "mutation_positions": [3, 17, 42],
      "mutation_count": 3,
      "bio_score": 0.82,
      "carbon_score": 0.74,
      "feasibility_score": 0.91,
      "final_score": 0.81
    }
  ],
  "_meta": {
    "disclaimer": "All scores are simulation proxies. Not wet-lab validated predictions.",
    "sort_order": "final_score DESC, bio_score DESC on tie"
  }
}
```

| Field | Type | Notes |
|-------|------|-------|
| `seed` | integer | Seed used (echoed or auto-generated if not supplied) |
| `total_generated` | integer | Always equals request `candidates` value |
| `weights_used` | object | Effective weights applied to ranking |
| `ranked_candidates` | array | Sorted by `final_score` desc; ties broken by `bio_score` desc |
| `ranked_candidates[].id` | string | UUID v4 |
| `ranked_candidates[].mutated_sequence` | string | Full amino acid sequence |
| `ranked_candidates[].mutation_positions` | array[int] | 0-indexed, sorted ascending |
| `ranked_candidates[].mutation_count` | integer | = len(mutation_positions) |
| `ranked_candidates[].bio_score` | float | [0.0, 1.0] |
| `ranked_candidates[].carbon_score` | float | [0.0, 1.0] |
| `ranked_candidates[].feasibility_score` | float | [0.0, 1.0] |
| `ranked_candidates[].final_score` | float | [0.0, 1.0] |
| `_meta.disclaimer` | string | Required proxy-label per FR-014 |
| `_meta.sort_order` | string | Documents tie-breaking rule per FR-008 |

**Error Responses**

| HTTP Status | Condition | Example body |
|-------------|-----------|--------------|
| 422 Unprocessable Entity | Validation failure | `{"detail": [{"loc": ["body", "base_sequence"], "msg": "String too short"}]}` |
| 422 Unprocessable Entity | Weights don't sum to 1.0 | `{"detail": "weights must sum to 1.0 (got 0.85, tolerance ±0.001)"}` |
| 422 Unprocessable Entity | Invalid amino acid chars | `{"detail": "base_sequence contains invalid characters: ['B', 'X']"}` |
| 422 Unprocessable Entity | Sequence too short | `{"detail": "base_sequence must be at least 50 characters (got 32)"}` |
| 500 Internal Server Error | All positions conserved / no mutable positions | `{"detail": "Cannot generate mutations: all positions are conserved"}` |

---

### GET /health

Liveness check for the dashboard to confirm API is running.

**Request**

```
GET /health
```

**Response 200 OK**

```json
{
  "status": "ok",
  "version": "1.0.0"
}
```

---

## Logging Contract

Every scoring stage MUST emit a structured log entry (Python `logging`, INFO level):

```json
{
  "candidate_id": "3f2504e0-...",
  "stage": "biological | carbon | feasibility | ranking",
  "input_values": { "...": "..." },
  "output_score": 0.82,
  "timestamp": "2026-02-24T14:30:00.123456Z"
}
```

Request-level log (at start of each `/generate` call):

```json
{
  "event": "generate_request",
  "candidates": 100,
  "mutation_rate": 0.05,
  "seed": 42,
  "timestamp": "2026-02-24T14:30:00.000000Z"
}
```

---

## BioNeMo Replacement Interface

The generation layer MUST conform to this interface to enable drop-in BioNeMo replacement:

```python
from typing import Protocol
import numpy as np

class GeneratorInterface(Protocol):
    def generate(
        self,
        base_sequence: str,
        mutation_rate: float,
        n_candidates: int,
        conserved_positions: list[int],
        rng: np.random.Generator,
    ) -> list[EnzymeCandidate]:
        ...
```

All BioNeMo integration points MUST be marked `# BioNeMo: replace with real inference`.
