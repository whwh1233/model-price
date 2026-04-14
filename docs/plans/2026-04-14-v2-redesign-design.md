# Model Price v2 — Complete Redesign

**Date**: 2026-04-14
**Status**: Accepted, ready for implementation
**Owner**: xiaobox
**Work branch**: `v2` (to be created from `release`)

---

## 1. Why we're rebuilding

Today's `release` branch works, but has four structural problems that no amount of incremental patching will fix:

1. **Flat data model**. `provider:model_id` is a leaf, not a root. Real models have a two-layer shape: a logical entity (e.g. "Claude Sonnet 4.5") offered by multiple providers (Anthropic, Bedrock, Azure, OpenRouter) at slightly different prices. Forcing this shape into one row per provider causes:
    - **D**: duplicate rows for the same logical model ("which Claude is the real one?")
    - **G**: no ground-truth list of "what models should be in the catalog", so missing models go undetected
    - **E**: capabilities/context/modalities are stored per-offering, so LiteLLM metadata mismatches repeatedly corrupt them (the 4.x fix in commit 650898d is a symptom, not the cure)
    - **C**: `cached_input` field has conflated semantics across providers (read hit vs creation vs write)

2. **Undifferentiated UI**. It's a virtual table with filters — functionally correct, but emotionally flat. Nothing in the experience creates a reason to come back or to recommend. Target users (independent devs, agent toolchain devs) are power users who reward speed and keyboard-first design; they get neither.

3. **No shareable URLs**. No `/m/:slug` detail route, no `/compare/:ids` route. That means zero SEO long-tail (the "`claude sonnet 4.5 price`" type of query is a goldmine for repeat traffic) and nothing to paste in V2EX / Twitter threads.

4. **Intuitive data distrust**. The maintainer's hunch ("something feels off") is almost certainly the flat data model leaking to the surface — same model at two prices, wrong capability chip, missing new release. Trust is the product; trust depends on correctness.

The v2 goal is to fix all four in one coordinated rebuild, not patch them one by one.

---

## 2. Product positioning

### 2.1 Scenario priority

Five canonical "why would I open a LLM price site" scenarios, ranked:

| Rank | Code | Scenario | Role |
|------|------|----------|------|
| 1 | **D** | Quick price lookup ("what's Sonnet cost?") | foundation |
| 2 | **A** | Side-by-side comparison | foundation |
| 3 | **C** | "Same-tier cheaper alternative" | killer differentiator |
| 4 | **B** | Cost estimator (my token volume → monthly bill) | retention hook |
| 5 | **E** | Price change / new model tracker | return-visit reason |

**D + A** are the ground floor — any failure here kills everything above.
**C** is the feature that makes this site different from every other LLM price tracker; nobody does "automatic same-capability-tier alternatives" well.
**B** is a strong retention driver once the foundation is solid.
**E** is postponed to post-v2 (it depends on maintaining a price history, which is a separate concern).

### 2.2 Target users

- **① Independent developers / indie hackers** — building side projects or SaaS, optimizing for $ per quality. Will tolerate and reward high information density.
- **③ Agent / toolchain developers** — people wiring up Claude Code, Cursor, dify, n8n, MCP stacks. They care about capability matrix (tool use, vision, context) more than exact price, and they want to **copy `model_id` straight into their config**.

Both groups are **keyboard-first power users** and **amplifiers** (they post on V2EX, Twitter, 小红书). Designing for them directly drives top-of-funnel growth.

Explicitly **not** targeting: non-technical users comparing ChatGPT subscriptions, procurement decision-makers who need SLA/compliance docs, or enterprise buyers. Serving those groups would dilute information density and alienate the primary audience.

### 2.3 Single point of breakthrough

**Cmd+K (⌘K) universal search + shareable deep-link URLs**, integrated into a keyboard-first zero-click workflow.

Inspiration: Linear, Raycast, GitHub command palettes.

Why this and not a visual "leaderboard / 擂台" view:
- Power users reward speed, not spectacle
- Cmd+K is a muscle-memory anchor (users who learn it come back for life)
- "`/m/claude-sonnet-4-5`" shareable URLs create SEO and social amplification as a free side effect
- A visual leaderboard built on incorrect data would be embarrassing; fix data first, add spectacle later if needed

---

## 3. UI blueprint

### 3.1 First-screen layout (desktop default)

```
┌──────────────────────────────────────────────────────────────┐
│  ⬡ Model Price                                     ⌘K Search │   minimal top bar
├──────────────────────────────────────────────────────────────┤
│                                                              │
│     Compare 600+ LLMs from 6 providers in one place.         │   one-line tagline
│     ┌──────────────────────────────────────────────┐  ⌘K    │
│     │ 🔍 Search model name or paste model_id…     │         │   always-visible hero
│     └──────────────────────────────────────────────┘         │
│                                                              │
│  [All makers ▾] [All families ▾] [Context ▾] [Sort ▾]        │   filter row
│  ◉ Text  ○ Vision  ○ Tool use  ○ Reasoning  ○ Audio          │   capability chips
│                                                              │
│  Showing 420 models                    [≡ Table] [▦ Cards]   │
├──────────────────────────────────────────────────────────────┤
│  Model                Maker     Ctx    In $/M  Out $/M  Cap  │
│  ──────────────────────────────────────────────────────────  │
│  ▸ Claude Sonnet 4.5  Anthropic 200K   $3.00   $15.00  T V R │   hover → "+" button
│  ▸ DeepSeek V3        DeepSeek  128K   $0.27   $1.10   T   R │
│  ▸ GPT-4o             OpenAI    128K   $2.50   $10.00  T V   │
│  ...(virtual scroll, dense rows)                             │
│                                                              │
│                            ╭──────────────────────╮          │
│                            │  Compare (2)   →    │             floating basket
│                            ╰──────────────────────╯          │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 Three user flows collapsing into one page

| User | Path |
|------|------|
| **New visitor (D quick lookup)** | Open → see hero search + table → type "sonnet" → table filters live → see price → done (0 or 1 action) |
| **① Indie dev (A comparison)** | Open → filter "Vision + 200K ctx" → 12 rows → sort by Input $/M → check 2–3 rows → floating basket → `/compare/...` |
| **③ Toolchain dev (returning power user)** | ⌘K → type "hai" → arrow-select Claude Haiku → ⌘C copies `anthropic:claude-haiku-4-5` → paste in Cursor config (total: ~3s) |

### 3.3 Detail surface: drawer AND page

- **Default**: click row name → **right-side drawer** slides in (list context preserved). URL syncs to `?m=claude-sonnet-4-5` so the state is shareable and back-button friendly.
- **Direct deep link / SEO**: `/m/claude-sonnet-4-5` renders the same component as a full page.
- **Drawer content**:
  - Full pricing matrix (input / output / cache read / cache write / batch / image / audio)
  - Capability chips + modality icons
  - `context_length` / `max_output_tokens` / family / maker
  - **Offering list**: all providers that serve this model, side-by-side prices (the visible cure for the D problem)
  - **Same-tier alternatives** (the C killer feature): 3 automatically-selected models with similar capability profile and lower price, each with a `−XX%` badge
  - "+ Add to compare" button
  - "Copy model_id" one-click

### 3.4 Compare surface

- `/compare/claude-sonnet-4-5-vs-deepseek-v3-vs-gpt-4o`
- Up to **4 entities** side-by-side
- Sections: pricing / capability matrix / context / modalities / alternative ranking
- "Copy as markdown table" to paste in docs

### 3.5 Interactions

- ⌘K opens command palette (same search as hero, but overlay mode)
- Type 2+ chars → instant filter
- ⌘/ shows keyboard cheat sheet
- Hover row → "+" button appears on right edge
- Click "+" or ⌘-click row → toggle in compare basket
- Shift-click for range selection
- Basket shows count; click → `/compare/...`
- All table columns keyboard-sortable

### 3.6 Visual direction

- Dense but breathable — row height 32–36px, generous letter-spacing on numbers (mono font)
- Numeric columns right-aligned, mono font
- Color-coded maker tags (6 distinct hues at low saturation)
- Dark theme first, light theme as fallback
- References: Linear, Raycast, Stripe Dashboard, Vercel Dashboard

---

## 4. Data architecture

### 4.1 Core idea

Two-layer model derived from **LiteLLM as the Single Source of Truth (SoT)**, with provider-sourced pricing overlays.

```
         ┌────────────────────────────────────────────────┐
         │  LiteLLM registry (Single Source of Truth)     │
         │  model_prices_and_context_window.json          │
         │  raw JSON fetched on every refresh             │
         └────────────────┬───────────────────────────────┘
                          │
                          ▼
         ┌────────────────────────────────────────────────┐
         │  Canonical Entity Layer                        │
         │  ─ canonical_id / slug                         │
         │  ─ family, maker                               │
         │  ─ context_length, max_output_tokens           │
         │  ─ capabilities, input/output modalities       │
         │  ─ primary_offering (from litellm_provider or  │
         │    AUTHORITY_BY_FAMILY override)               │
         └────────────────┬───────────────────────────────┘
                          │  reverse-lookup via LiteLLM aliases
                          ▼
  ┌──────────────┬──────────────┬──────────────┬──────────────┬──────────────┬──────────────┐
  │  Anthropic   │ AWS Bedrock  │  Azure       │  OpenAI      │  OpenRouter  │  Google /xAI │
  │  fetch()     │  fetch()     │  fetch()     │  fetch()     │  fetch()     │  fetch()     │
  └──────┬───────┴──────┬───────┴──────┬───────┴──────┬───────┴──────┬───────┴──────┬───────┘
         │              │              │              │              │              │
         └──────────────┴──────────────┴──┬───────────┴──────────────┴──────────────┘
                                          ▼
                      ┌──────────────────────────────────────┐
                      │  Offering Merger                     │
                      │  Each provider record → canonical_id │
                      │   → attached as Offering             │
                      └───────────────┬──────────────────────┘
                                      │
                                      ▼
                      ┌──────────────────────────────────────┐
                      │  Drift Report (auto)                 │
                      │  ─ unmatched_provider_models         │
                      │  ─ price_drift > 5% vs LiteLLM       │
                      │  ─ new_entities / removed_entities   │
                      │  ─ orphan (LiteLLM-only) entities    │
                      └──────────────────────────────────────┘
```

### 4.2 Why LiteLLM is the right SoT

- **Community maintained, weekly cadence** — new flagship models typically land within 1–5 days of announcement. You don't maintain the list.
- **Already canonical** — each key (`claude-sonnet-4-5`, `gpt-4o`) is the logical name; all provider aliases (`anthropic/...`, `bedrock/anthropic.claude-sonnet-4-5-v1:0`, `azure/gpt-4o`) resolve to it. LiteLLM has already done the deduplication work.
- **Complete field set** — `input_cost_per_token`, `output_cost_per_token`, `cache_read_input_token_cost`, `cache_creation_input_token_cost`, `max_input_tokens`, `max_output_tokens`, `supports_vision`, `supports_function_calling`, `supports_tool_choice`, `supports_response_schema`, `supports_audio_input`, `supports_pdf_input`, `mode`, `litellm_provider`.
- **Clean cache semantics** — `cache_read_input_token_cost` vs `cache_creation_input_token_cost` are explicitly separated, solving the C problem as a free side effect.
- **Battle tested** — LangChain, LlamaIndex, Dify, n8n, and most AI SDKs use it for accounting. If it's wrong, the whole ecosystem notices quickly.

### 4.3 Entity schema (v2)

```json
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
  "sources": ["litellm", "anthropic", "aws_bedrock", "openrouter"],
  "last_refreshed": "2026-04-14T15:00:00Z"
}
```

### 4.4 Offering schema (v2)

```json
{
  "entity_id": "claude-sonnet-4-5",
  "provider": "anthropic",
  "provider_model_id": "claude-sonnet-4-5-20250929",
  "pricing": {
    "input": 3.00,
    "output": 15.00,
    "cache_read": 0.30,
    "cache_write": 3.75,
    "image_input": null,
    "audio_input": null,
    "audio_output": null,
    "embedding": null
  },
  "batch_pricing": { "input": 1.50, "output": 7.50 },
  "availability": "ga",
  "region": null,
  "notes": null,
  "last_updated": "2026-04-14T14:58:00Z",
  "source": "provider_api"
}
```

`source` is one of: `provider_api`, `provider_scrape`, `litellm_fallback`.

### 4.5 Refresh pipeline

```
Step 1  Fetch LiteLLM raw JSON from github.com/BerriAI/litellm/main
         → parse into an in-memory registry keyed by canonical_id
         → build alias → canonical_id reverse index

Step 2  For each LiteLLM entry, build an Entity skeleton
         (name, family, context, capabilities, modalities)

Step 3  Run the existing 6 provider fetchers in parallel (unchanged interface)

Step 4  For each provider record (provider, provider_model_id, pricing):
         a. Look up canonical_id via LiteLLM alias table
         b. On hit: attach as Offering to the matching Entity
         c. On miss: record in drift.unmatched_provider_models

Step 5  For each Entity with zero provider-sourced Offerings:
         synthesize a Offering from LiteLLM's own pricing (source = litellm_fallback)

Step 6  For each Entity, set primary_offering_provider:
         a. Read LiteLLM's `litellm_provider` field
         b. If ambiguous or missing, fall back to AUTHORITY_BY_FAMILY map

Step 7  Compute drift report (diffs from last refresh)

Step 8  Write:
         backend/data/v2/entities.json
         backend/data/v2/offerings.json
         backend/data/v2/drift.json
         backend/data/v2/index.json   (summary stats)
```

### 4.6 Authority override map (hardcoded, ~15 lines)

```python
# Only for families where LiteLLM's litellm_provider is ambiguous or wrong.
# One-shot rule, not per-model data. Extending it is a rare event.
AUTHORITY_BY_FAMILY = {
    "claude":  ["anthropic", "aws_bedrock", "azure_openai", "openrouter"],
    "gpt":     ["openai", "azure_openai", "openrouter"],
    "gemini":  ["google_gemini", "openrouter"],
    "grok":    ["xai", "openrouter"],
    "llama":   ["aws_bedrock", "openrouter"],
    "mistral": ["openrouter"],
    "deepseek": ["openrouter"],
}
```

Everything not in this table reads directly from LiteLLM's `litellm_provider`.

### 4.7 Drift report (self-healing data quality)

Written to `backend/data/v2/drift.json` on every refresh. Schema:

```json
{
  "generated_at": "2026-04-14T15:00:00Z",
  "counts": {
    "entities_total": 612,
    "entities_new": 3,
    "entities_removed": 1,
    "offerings_total": 1420,
    "unmatched_provider_models": 7,
    "orphan_entities": 24,
    "price_drift_items": 2
  },
  "unmatched_provider_models": [
    { "provider": "openrouter", "model_id": "some/weird-alias", "tried_aliases": [...] }
  ],
  "price_drift": [
    { "entity": "claude-sonnet-4-5", "provider": "openrouter", "field": "input", "provider_value": 3.30, "litellm_value": 3.00, "delta_pct": 10.0 }
  ],
  "new_entities": ["gemini-3-pro", "gpt-5-1-mini", "claude-opus-4-6"],
  "removed_entities": ["claude-3-opus-20240229"],
  "orphan_entities": ["some-model-only-in-litellm"]
}
```

Consumed by `/api/v2/drift` (internal only) and by the background scheduler that optionally posts a summary to a webhook (Discord / Feishu) if configured via env var. If the webhook is not set, the file just sits there.

---

## 5. v2 API contract (draft, frozen at Phase 0)

Base path: `/api/v2`

### 5.1 Endpoints

| Method | Path | Purpose | Returns |
|--------|------|---------|---------|
| `GET` | `/api/v2/entities` | List entities with optional filters | `Entity[]` (primary_offering embedded) |
| `GET` | `/api/v2/entities/:slug` | Single entity + all offerings + alternatives | `EntityDetail` |
| `GET` | `/api/v2/search?q=&limit=10` | Cmd+K fast search | `SearchResult[]` |
| `GET` | `/api/v2/compare?ids=slug1,slug2,...` | Compare up to 4 entities | `CompareResult` |
| `GET` | `/api/v2/stats` | Dashboard stats | `StatsV2` |
| `GET` | `/api/v2/drift` | Latest drift report | `DriftReport` |
| `POST` | `/api/v2/refresh` | (internal) trigger refresh pipeline | `{ ok, counts }` |

### 5.2 Query parameters on `/api/v2/entities`

- `q` — full-text over name / family / maker
- `family` — "Claude", "GPT", "Gemini", ...
- `maker` — "Anthropic", "OpenAI", ...
- `capability` — any of `text|vision|audio|tool_use|reasoning|function_calling|image_generation`
- `min_context` — e.g. `200000`
- `max_input_price` — e.g. `5.0`
- `sort` — `name|input|output|context|input_cheapest|output_cheapest`
- `order` — `asc|desc`

### 5.3 Response example: `/api/v2/entities/claude-sonnet-4-5`

```json
{
  "entity": { /* Entity schema §4.3 */ },
  "offerings": [
    { /* Offering schema §4.4 */ },
    { /* ... */ }
  ],
  "alternatives": [
    { "canonical_id": "deepseek-chat-v3", "delta_input_pct": -90, "delta_output_pct": -92, "capability_overlap": 0.83 },
    { "canonical_id": "gpt-4o-mini", "delta_input_pct": -95, "delta_output_pct": -96, "capability_overlap": 0.75 },
    { "canonical_id": "gemini-2-5-flash", "delta_input_pct": -93, "delta_output_pct": -95, "capability_overlap": 0.78 }
  ]
}
```

Alternatives are computed server-side using a similarity function over `capabilities ∩ capabilities` normalized by union size, filtered by `input_price < reference_input_price`, ranked by capability overlap × price delta.

### 5.4 Legacy compatibility

`/api/models`, `/api/providers`, `/api/families`, `/api/stats` remain live through **2026-04-28** (two weeks post-cutover), then are removed in a cleanup commit.

---

## 6. Implementation plan — parallel tracks

All work happens on branch `v2` (created from `release`).

### Phase 0 — Contract freeze (Day 1)

1. Commit this design doc on `release` (done)
2. Create `v2` branch from `release`
3. Author `backend/data/v2/fixtures/sample.json` — 5 to 10 fully-realized entities including Claude Sonnet 4.5, GPT-4o, Gemini 2.5 Pro, DeepSeek V3, Grok 4, one OpenRouter-only fringe model (edge case)
4. Define stub FastAPI routes for `/api/v2/*` in `backend/main.py`, each returning fixture data
5. Publish the contract in `docs/plans/v2-api-contract.md` (short summary, schemas reference this doc)

Exit criteria: both tracks can proceed independently without waiting on each other.

### Phase 1 — Backend data layer (Days 2–6, parallel with Phase 2)

Files to create:

- `backend/services/litellm_registry.py`
  - Fetches `https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json`
  - Parses entries, builds alias → canonical_id reverse index
  - Caches raw JSON in `backend/data/v2/cache/litellm_registry.json` with ETag/last-modified guards
- `backend/services/canonical.py`
  - `resolve(provider: str, provider_model_id: str) -> str | None`
  - Handles prefix stripping, dash-slash normalization, date suffix stripping
- `backend/services/offering_merger.py`
  - Consumes all provider fetch outputs + LiteLLM registry
  - Produces `Entity` + `Offering` lists
  - Sets `primary_offering_provider` using LiteLLM + authority override
- `backend/services/drift_reporter.py`
  - Diffs against previous refresh
  - Emits `drift.json`
- `backend/models_v2.py` — Pydantic models for `Entity`, `Offering`, `EntityDetail`, `CompareResult`, `DriftReport`
- `backend/api_v2.py` — FastAPI router with all `/api/v2/*` endpoints

Files to modify:

- `backend/providers/*.py` — each provider's `fetch()` still returns raw price/model records; no logic change needed, only the shape of the downstream merger
- `backend/main.py` — mount the new `api_v2` router in addition to the existing v1 router
- `backend/services/refresh_scheduler.py` — update to also run the v2 pipeline

### Phase 2 — Frontend rebuild (Days 2–8, parallel with Phase 1)

Route structure (new; uses `react-router-dom` which is already in `dependencies`):

- `/` — main list view (hero search + filters + table)
- `/m/:slug` — full-page entity detail
- `/compare/:ids` — compare page (comma-separated slugs, max 4)

Components to create:

- `components/CommandPalette.tsx` — ⌘K overlay, fuzzy search, keyboard navigation
- `components/HeroSearch.tsx` — always-visible search with animated placeholder
- `components/EntityTable.tsx` — replaces `VirtualTable`, denser rows, hover "+" button
- `components/EntityDrawer.tsx` — right-side slide-in detail panel
- `pages/EntityPage.tsx` — full-page version of drawer content
- `pages/ComparePage.tsx` — side-by-side compare, up to 4 entities
- `components/CompareBasket.tsx` — floating corner basket with count
- `components/FilterBar.v2.tsx` — maker / family / capability chips / sort
- `components/AlternativesList.tsx` — "same-tier cheaper" cards with `−XX%` badges

Hooks to create (splitting the current bloated `useModels`):

- `hooks/useEntities.ts` — list + filters + sort (no cache/error/sync logic)
- `hooks/useEntity.ts` — single entity by slug
- `hooks/useSearch.ts` — debounced search for Cmd+K
- `hooks/useCompareBasket.ts` — local state for compare selection
- `hooks/useFallbackData.ts` — isolated fallback.json logic (inherited from release)

Visual system:

- `src/styles/tokens.css` — design tokens (spacing, color, typography scale, radii)
- Dark theme first, light theme `@media (prefers-color-scheme: light)`
- Mono font for numbers (JetBrains Mono or similar)
- 6 maker hues at low saturation

Libraries to add (keep minimal):

- `cmdk` (~5KB gzipped) for the command palette primitive — or hand-rolled; decide during implementation
- `react-router-dom` — already present

Files to remove or deprecate (inside v2 branch only):

- Current `App.css` custom classes — replaced by tokens
- Current `useModels.ts` — split into the hooks above (fallback logic preserved)

### Phase 3 — Integration & validation (Days 7–9)

- Frontend stops using `fixtures/sample.json`, starts hitting real `/api/v2/*`
- Smoke test all routes: `/`, `/m/claude-sonnet-4-5`, `/compare/...`, `/api/v2/search?q=...`
- Read `drift.json`, verify unmatched count is below threshold (target: <10 for top 50 models)
- Spot-check Claude Sonnet 4.5 / GPT-4o / Gemini 2.5 Pro / DeepSeek V3 / Grok 4 against official docs
- Lighthouse performance pass (target: FCP < 1.0s, LCP < 2.0s on desktop, interactive < 2.0s)
- Keyboard-only usability pass (Tab, ⌘K, Enter, ⌘C, ⌘D, Esc all work)
- `frontend/scripts/build-fallback.mjs` updated to emit v2-shaped fallback (entity+offering instead of flat models)

### Phase 4 — Deploy & cutover (Day 10)

- Push `v2` branch to origin
- Vercel auto-creates a preview deployment for `v2`
- Final smoke test on the preview URL
- Merge `v2` → `release`:
  - Backend now serves both `/api/models` (v1) and `/api/v2/*` (v2)
  - Frontend `config.ts` API_BASE flips from `/api` to `/api/v2`
  - `vercel.json` rewrite target remains `https://model-price.onrender.com/api/:path*` (works for both v1 and v2 since path is preserved)
- Render auto-deploys backend, Vercel auto-deploys frontend
- Post-deploy canary: hit `/api/v2/stats` and `/api/v2/entities?limit=5` from the production URL
- Deprecation window starts: 2026-04-14 → 2026-04-28

### Phase 5 — Cleanup (2026-04-28)

- Delete `/api/models`, `/api/providers`, `/api/families`, `/api/stats` from `backend/main.py`
- Delete v1 PricingService flat-data code paths
- Delete `backend/data/providers/*.json` and `backend/data/index.json` (replaced by `data/v2/*`)
- Commit: "chore: remove v1 API after 2-week deprecation"

---

## 7. Success criteria

### 7.1 Data quality (must-hit before cutover)

- **Zero duplicate rows** for any of the top 50 models (one entity, multiple offerings in the drawer)
- **Drift report**: `unmatched_provider_models` count for the top 50 models by popularity = 0
- **No null core fields**: every entity has non-null `capabilities`, `context_length`, `max_output_tokens`, `input_modalities`, `output_modalities`
- **Spot-check match** for 10 reference models (Claude Sonnet 4.5, Claude Opus 4.6, GPT-4o, GPT-4.1, o3, Gemini 2.5 Pro, Gemini 2.5 Flash, DeepSeek V3, Grok 4, Llama 4 Scout) — pricing within ±1% of official docs
- **Capability correctness**: manual verification that `supports_vision`, `supports_function_calling`, `supports_tool_choice` are correct for the above 10 reference models

### 7.2 Performance (must-hit before cutover)

- First contentful paint < 1.0s on cold visit (fallback.json seeds instantly)
- Cmd+K open < 100ms
- Search returns results < 50ms for 600+ entities
- Full keyboard path "open → search → copy model_id" completes in under 5 seconds
- Lighthouse score ≥ 90 across Performance / Accessibility / Best Practices / SEO

### 7.3 Experience (soft validation, post-launch)

- Every model has a clean shareable URL `/m/:slug` indexable by search engines
- Every comparison has a clean shareable URL `/compare/:ids`
- Dark theme looks deliberately designed, not default-ugly
- Mobile: table collapses to card list, search still reachable

### 7.4 Adoption (informal, post-launch)

- Increase in 7-day repeat visits
- Any organic mention on V2EX / Twitter / 小红书 captured as signal

---

## 8. Explicit non-goals (YAGNI fence)

These are **not** in v2. They are either postponed to v3 or intentionally dropped.

- ❌ No manual model registry / YAML list maintained by humans
- ❌ No user accounts, login, or personalization
- ❌ No database — still JSON files for portability on Render free tier
- ❌ No price history / charts / changelog (postponed)
- ❌ No visual "leaderboard / 擂台" view — data must be rock-solid first, and spectacle without trust hurts
- ❌ No cost estimator page as a standalone feature — it lives inside the drawer (future enhancement)
- ❌ No SSR/SSG of `/m/:slug` pages — SPA with proper meta tags is enough for now; revisit in v3 if SEO demands it
- ❌ No i18n beyond keeping whatever zh/en the current site has
- ❌ No mobile-first rework — desktop first, mobile degrades gracefully
- ❌ No migration of `/api/models` semantics — v1 and v2 coexist for two weeks, then v1 is deleted

---

## 9. Open implementation questions (decided during build, not now)

- `cmdk` library vs hand-rolled palette (size vs fit)
- Drawer state: route-driven (`?m=slug`) or React state only
- SSG of 600 detail routes at Vercel build time (nice-to-have, adds build time)
- Drift-report webhook channel (Discord / Feishu / none)
- Cache strategy for LiteLLM fetches (ETag vs TTL)
- Whether to keep `react-router-dom` or use simpler path-based routing

Each of these is small, local, and reversible. Resolving them in code review beats speculating now.

---

## 10. Appendix — current state references

- `frontend/src/hooks/useModels.ts:1–587` — bloated hook to be split in Phase 2
- `frontend/src/App.tsx:1–148` — to be replaced with route shell
- `frontend/src/components/VirtualTable.tsx` — replaced by `EntityTable.tsx`
- `backend/services/pricing.py:216` — `extract_model_family` logic to be replaced by LiteLLM-derived family mapping
- `backend/services/metadata_fetcher.py` — to be replaced by `litellm_registry.py`
- `backend/providers/*.py` — unchanged interface, lightly adjusted output shape
- `backend/data/providers/*.json` — deleted in Phase 5
- `.github/workflows/keepalive.yml` — continues to work, no changes needed
- `frontend/public/fallback.json` — regenerated with v2 shape in Phase 3
