# v2 API Contract

**Status**: frozen at Phase 0
**Base path**: `/api/v2`
**Fixture source of truth**: `backend/data/v2/fixtures/sample.json`
**Authoritative design**: `docs/plans/2026-04-14-v2-redesign-design.md` §4–§5

All response shapes below are derived directly from `sample.json`. Frontend MAY import the fixture file during development; backend MUST return responses with identical field names and types.

---

## Units and conventions

- **All prices are per 1,000,000 tokens** (USD floating point). Backend converts from LiteLLM's per-token units before serializing. Frontend performs zero unit math.
- **Token counts** (`context_length`, `max_output_tokens`) are integers.
- **Timestamps** are ISO 8601 strings in UTC (`2026-04-15T00:00:00Z`).
- **Missing pricing components** use `null`, never `0` (zero is a valid price for some free tiers).
- **Slugs** are lowercase, kebab-case, stable across refreshes (`claude-sonnet-4-5`, `gpt-4o-mini`).

---

## Endpoints

### `GET /api/v2/entities`

List entities with optional filters.

**Query parameters** (all optional):

| Name | Type | Example |
|---|---|---|
| `q` | string | `sonnet` |
| `family` | string | `Claude` |
| `maker` | string | `Anthropic` |
| `capability` | string | `vision` |
| `min_context` | int | `200000` |
| `max_input_price` | float | `5.0` |
| `sort` | string | `name` / `input` / `output` / `context` |
| `order` | string | `asc` / `desc` |

**Response**: `EntityListItem[]`

Each item contains the full `Entity` fields (see §4.3 of design doc) plus an embedded `primary_offering` (the Offering from the `primary_offering_provider`). It does NOT include the full `offerings[]` array or `alternatives[]` — those belong to the detail endpoint.

```json
[
  {
    "canonical_id": "claude-sonnet-4-5",
    "slug": "claude-sonnet-4-5",
    "name": "Claude Sonnet 4.5",
    "family": "Claude",
    "maker": "Anthropic",
    "context_length": 200000,
    "max_output_tokens": 64000,
    "capabilities": ["text", "vision", "tool_use", "reasoning", "function_calling"],
    "input_modalities": ["text", "image"],
    "output_modalities": ["text"],
    "mode": "chat",
    "is_open_source": false,
    "primary_offering_provider": "anthropic",
    "sources": ["litellm", "anthropic", "aws_bedrock", "azure_openai", "openrouter"],
    "last_refreshed": "2026-04-15T00:00:00Z",
    "primary_offering": {
      "provider": "anthropic",
      "provider_model_id": "claude-sonnet-4-5-20250929",
      "pricing": {
        "input": 3.0,
        "output": 15.0,
        "cache_read": 0.3,
        "cache_write": 3.75,
        "image_input": null,
        "audio_input": null,
        "audio_output": null,
        "embedding": null
      },
      "batch_pricing": { "input": 1.5, "output": 7.5 },
      "availability": "ga",
      "region": null,
      "notes": null,
      "last_updated": "2026-04-15T00:00:00Z",
      "source": "provider_api"
    }
  }
]
```

---

### `GET /api/v2/entities/:slug`

Single entity with all offerings and alternatives.

**Path parameter**: `slug` (e.g. `claude-sonnet-4-5`)

**Response**: `EntityDetail`

```json
{
  "entity": { /* same fields as list item, without primary_offering */ },
  "offerings": [ /* full Offering[] for this entity */ ],
  "alternatives": [
    {
      "canonical_id": "deepseek-chat-v3",
      "name": "DeepSeek V3",
      "delta_input_pct": -91.0,
      "delta_output_pct": -92.7,
      "capability_overlap": 0.8
    }
  ]
}
```

**404** if slug not found.

---

### `GET /api/v2/search`

Fast search for Cmd+K palette.

**Query parameters**:

| Name | Type | Required | Default |
|---|---|---|---|
| `q` | string | yes | — |
| `limit` | int | no | `10` |

**Response**: `SearchResult[]`

```json
[
  {
    "canonical_id": "claude-sonnet-4-5",
    "slug": "claude-sonnet-4-5",
    "name": "Claude Sonnet 4.5",
    "family": "Claude",
    "maker": "Anthropic",
    "primary_input_price": 3.0,
    "primary_output_price": 15.0
  }
]
```

Matches by substring on `name`, `canonical_id`, and `family` (case-insensitive). Results sorted by: exact match first, then starts-with, then contains.

---

### `GET /api/v2/compare`

Side-by-side comparison for up to 4 entities.

**Query parameters**:

| Name | Type | Required | Notes |
|---|---|---|---|
| `ids` | string | yes | Comma-separated slugs, max 4 |

**Response**: `CompareResult`

```json
{
  "entities": [ /* EntityDetail[] for each requested slug */ ],
  "common_capabilities": ["text", "tool_use"],
  "requested_ids": ["claude-sonnet-4-5", "gpt-4o", "gemini-2-5-pro"],
  "missing_ids": []
}
```

Missing slugs are reported in `missing_ids` rather than 404-ing the whole request.

---

### `GET /api/v2/stats`

Dashboard counters.

**Response**: `StatsV2`

```json
{
  "total_entities": 8,
  "total_offerings": 21,
  "makers": 5,
  "families": 5,
  "last_refresh": "2026-04-15T00:00:00Z",
  "fixture": true
}
```

The `fixture: true` flag is present only while Phase 0 stub routes are serving fixture data; real Phase 1 responses omit it.

---

### `GET /api/v2/drift`

Self-healing data quality report.

**Response**: `DriftReport`

See design doc §4.7 for full schema.

---

### `POST /api/v2/refresh` (internal, optional auth)

Triggers the v2 refresh pipeline. Not exposed in the UI. Phase 1 wires this up; Phase 0 stub returns `{ "ok": false, "reason": "phase_0_stub" }`.

---

## Frontend consumption guidelines

1. **Types** should be generated manually from this doc into `frontend/src/types/v2.ts` during Phase 2. Keep field names byte-for-byte identical to the JSON.
2. **For local development**, frontend may import `/public/fixtures/v2-sample.json` (symlinked from `backend/data/v2/fixtures/sample.json` via build script) instead of hitting the backend — useful when Render is cold.
3. **Unit handling**: never divide or multiply prices by 1_000_000. Display as-is.
4. **Null pricing fields**: render as `—` (em dash), not `$0` or "free".
5. **Slug in URLs**: always use `slug`, never `canonical_id`. They are equal today but may diverge in v3 (e.g., if versioned slugs are introduced).

---

## Backwards compatibility

- `v1` endpoints (`/api/models`, `/api/providers`, `/api/families`, `/api/stats`, `/api/refresh/metadata`) were removed on **2026-04-15**. Calling them returns 404.
- `POST /api/refresh` remains as a compatibility alias that internally runs the v2 refresh pipeline. The `?provider=...` query parameter is accepted for backwards compatibility but ignored — v2 always refreshes the whole store atomically.
- `GET /api/health` is preserved (with a v2-shaped payload) because `.github/workflows/keepalive.yml` depends on it.

---

## Error shape

All v2 error responses use this uniform shape:

```json
{
  "error": {
    "code": "not_found",
    "message": "Entity 'foo-bar' not found",
    "details": null
  }
}
```

Error codes: `not_found`, `bad_request`, `too_many_ids`, `internal_error`.
