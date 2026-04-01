# AI Architect — CLAUDE.md

## My Assignment

I am **Dev B** on the Knit AI Onboarding System.
My component is the **JSON Preview Generator** — Component 2 of the 3-part pipeline:

```
[Dev A] AI Bundle Classifier
    ↓  ClassificationPayload (session_id, bundle_key, conversation_history)
[Dev B] JSON Preview Generator  ← THIS IS ME
    ↓  AppPayload (generation_json + dummy_data_json)
[Dev C] JSON App Generator
    ↓  Provisioned Workspace
```

---

## Project Overview

**Stack:** Python · FastAPI · LangGraph · Pydantic v2 · pytest

**Entry Point:** `src/main.py`
**Config:** `src/core/config.py`
**API App:** `src/api/app.py`

**My Primary Directories:**
```
src/agents/preview_generator/    # The entire preview generator pipeline
src/api/routers/preview.py       # HTTP endpoint
src/orchestrators/preview_flow.py
docs/features/                   # Feature documentation I own
tests/integration/test_preview_generator_flow.py
tests/integration/test_dev_a_to_preview_handoff.py
```

---

## Codebase Map

### API Layer
| File | Purpose |
|------|---------|
| `src/api/routers/session.py` | `POST /sessions`, `POST /sessions/{id}/reply`, `POST /sessions/{id}/confirm` |
| `src/api/routers/preview.py` | `POST /sessions/{id}/preview` — my endpoint |
| `src/api/deps.py` | DI: `get_preview_flow()`, `get_session_repository()`, `get_conversation_repository()` |
| `src/api/schemas/` | Pydantic request/response schemas |

### Orchestration
| File | Purpose |
|------|---------|
| `src/orchestrators/conversation_flow.py` | Dev A's conversation + bundle classification |
| `src/orchestrators/preview_flow.py` | Calls `PreviewGeneratorService`, assembles `AppPayload` |

### Preview Generator Pipeline (`src/agents/preview_generator/`)
| File | Purpose |
|------|---------|
| `state.py` | `PreviewGeneratorState` — shared LangGraph working memory |
| `schemas.py` | `UserContext`, `KpiMetric`, `GenerationJson`, `DummyDataJson`, `PreviewOutput` |
| `pipeline.py` | LangGraph graph compilation + conditional retry edge |
| `service.py` | `PreviewGeneratorService.generate()` — thin wrapper over compiled graph |
| `bundles/registry.py` | `ALL_FEATURE_FLAGS` (69), `BUNDLE_REGISTRY` (9 bundles), `METRICS_CATALOG` (17 KPIs) |
| `edit/` | Phase 2 placeholder — not yet implemented |

### Pipeline Nodes (`src/agents/preview_generator/nodes/`)
| Node File | LangGraph Node Name | What It Does |
|-----------|--------------------|----|
| `extract_context.py` | `extract_user_context` | Keyword + regex scan of conversation → `UserContext` |
| `resolve_flags.py` | `resolve_bundles_to_flags` | Bundle key → feature flags + permission_services + landing_pages |
| `data_tier.py` | `select_data_tier` | Known bundle → Tier 1; unknown → Tier 3 |
| `sample_data.py` | `generate_sample_data` | Build employees, projects, tickets, weaves |
| `kpi.py` | `build_kpi_metrics` | Bundle defaults + conversation signals → KPI list |
| `validate.py` | `validate_schema` | Check minimum data; route retry or emit |
| `emit.py` | `emit_preview` | Assemble `GenerationJson` + `DummyDataJson` → `PreviewOutput` |

### Pipeline DAG
```
extract_user_context
  ↓
resolve_bundles_to_flags
  ↓
select_data_tier
  ↓
generate_sample_data
  ↓
build_kpi_metrics
  ↓
validate_schema ──[valid]──────────────────→ emit_preview → END
      ↑                                             ↑
      └──[invalid, retry_count < 2]─────────────────┘
      └──[invalid, retries exhausted]────────────────┘
```

### Domain Models
| File | Key Model |
|------|----------|
| `src/domain/models/session.py` | `Session` — `confirmed`, `selected_bundle_key`, + pipeline state fields added by Lars (`accumulated_extraction`, `latest_classification`, `latest_recommendation`, `clarification_turn_count`) |
| `src/domain/models/app_payload.py` | `AppPayload` — what the HTTP response wraps |
| `src/domain/models/conversation.py` | `ConversationMessage` |
| `src/repositories/session_repository.py` | In-memory store for sessions |
| `src/repositories/conversation_repository.py` | In-memory store for messages |

### Other Agents (not my work — read-only context)
| Directory | Owner | Purpose |
|-----------|-------|---------|
| `src/agents/interpreter/` | Dev A | AI Bundle Classifier |
| `src/agents/replier/` | Dev A | Clarification responder |
| `src/agents/app_generator/` | Dev C | Workspace provisioner |

### Docs I Own
| File | Covers |
|------|--------|
| `docs/features/preview_schema_definition.md` | JSON output contracts |
| `docs/features/generate_preview_configuration.md` | Pipeline architecture |
| `docs/features/module_kpi_mapping_engine.md` | Flag + KPI resolution logic |
| `docs/features/preview_data_population.md` | Sample data generation |
| `docs/features/preview_generator_changelog.md` | Implementation log |
| `docs/features/preview_generator.md` | Original feature overview |

### Key Reference Files
| File | Purpose |
|------|---------|
| `JSON_Preview_Plan.md` | Full design spec for my component |
| `PLAN.md` | System-level architecture |
| `EOD.md` | End-of-day progress log (most recent: 2026-03-24) |
| `REVIEW.md` | Branch review — what changed vs `internal-dev` |
| `docs/api-mocks.json` | Source of truth for the 69 feature flags |
| `catalog/bundles.json` | Bundle catalog (Dev A's classification output uses these keys) |

---

## Data Contract with Dev A

Dev A produces a confirmed session with:
- `session.confirmed = True`
- `session.selected_bundle_key` — one of the `BundleType` enum values (updated 2026-03-26 by Lars)

**Current `BundleType` catalog keys (from `src/domain/enums/bundle_type.py`):**
```
hr_management, ticketing, project_mgmt, finance, marketing, sales,
healthcare, legal_services, construction_real_estate, education,
all_microservices, generic
```

My endpoint reads both and calls the pipeline. **Catalog-to-registry translation happens inside `resolve_flags.py`:**
```
hr_management → hr_hub        (registry key unchanged)
project_mgmt  → project_mgmt  (identity)
ticketing     → ticketing     (identity)
finance       → (unknown → Tier 3)
marketing     → (unknown → Tier 3)
sales         → (unknown → Tier 3)
healthcare    → (unknown → Tier 3)
legal_services         → (unknown → Tier 3)
construction_real_estate → (unknown → Tier 3)
education     → (unknown → Tier 3)
all_microservices → (unknown → Tier 3)
generic       → (unknown → Tier 3)
```

> **Note:** Old catalog keys (`project_ops`, `field_service`, `asset_mgmt`) are retired. The
> `_CATALOG_TO_REGISTRY` map in `resolve_flags.py` must be updated as part of Phase 2.

## Data Contract with Dev C

I produce `AppPayload` with two top-level dicts:

**`generation_json`** — workspace configuration:
```json
{
  "schema_version": "1.0",
  "bundle_key": "project_mgmt",
  "feature_flags": [/* 69 flags, {id, name, description, isEnabled, module} */],
  "modules": ["Projects", "Dashboard", "KPI", "Chat"],
  "config": {
    "permission_services": ["projects", "kpi", "notifications"],
    "landing_pages": [{"id": 108, "module": "Projects", ...}]
  }
}
```

**`dummy_data_json`** — sample data stores:
```json
{
  "bundle_key": "project_mgmt",
  "session_id": "uuid",
  "company_name": "Acme Corp",
  "stores": {
    "kpis": [{"key": "on_time_delivery_rate", "label": "...", "type": "percentage", "sample_value": 87.5}],
    "dashboard_widgets": [],
    "tasks": [/* projects for project_mgmt */],
    "milestones": [/* or tickets/queues for ticketing/hr_hub */]
  }
}
```

Store key mapping per bundle:
| Bundle | Primary Store | Secondary Store |
|--------|--------------|----------------|
| `project_mgmt` | `tasks` | `milestones` |
| `ticketing` | `tickets` | `queues` |
| `hr_hub` | `tickets` | `queues` |
| `weaves` | `weaves` | — |

---

## Accomplished Tasks (Phase 1 — COMPLETE)

### Core Pipeline
- [x] `PreviewGeneratorState` typed LangGraph state definition
- [x] `extract_user_context` node — keyword + regex extraction (company, industry, teams, roles, work types, key phrases)
- [x] `resolve_bundles_to_flags` node — catalog→registry translation, flag resolution, addon recursion
- [x] `select_data_tier` node — Tier 1 (known bundle) / Tier 3 (fallback)
- [x] `generate_sample_data` node — industry-aware employees, projects, tickets, weaves (deterministic)
- [x] `build_kpi_metrics` node — bundle defaults + conversation-signal boosting
- [x] `validate_schema` node — minimum data checks + retry routing (max 2 retries)
- [x] `emit_preview` node — assembles `GenerationJson` + `DummyDataJson`
- [x] `pipeline.py` — LangGraph graph compiled with conditional retry edge
- [x] `service.py` — `PreviewGeneratorService.generate()` wrapper
- [x] `bundles/registry.py` — 69 feature flags, 9 bundles, 17 KPIs

### Integration
- [x] `preview.py` router — passes full `conversation_history` to pipeline (not empty)
- [x] `preview_flow.py` — assembles `AppPayload` directly, bypasses `AppGeneratorService`
- [x] `deps.py` — removed stale `TemplateRepository` dependency
- [x] `session.py` — fixed critical bug: `selected_bundle_key` now persisted after `process_turn`

### Tests
- [x] `tests/integration/test_preview_generator_flow.py` — 45 tests (all bundles, store names, flags, KPIs, company extraction, empty history, Tier 3 fallback)
- [x] `tests/integration/test_dev_a_to_preview_handoff.py` — 15 tests (HTTP layer, session validation, full chain)
- [x] 60 integration tests passing, ~3 seconds

### Documentation
- [x] `docs/features/preview_schema_definition.md`
- [x] `docs/features/generate_preview_configuration.md`
- [x] `docs/features/module_kpi_mapping_engine.md`
- [x] `docs/features/preview_data_population.md`
- [x] `docs/features/preview_generator_changelog.md`

---

## Known Issues / In Progress

### [BREAKING] Catalog Key Mismatch (from Lars's 2026-03-26 commit)
- **Problem:** `BundleType` enum rewritten — Dev A now sends `hr_management`, `project_mgmt`, `ticketing` etc. The old `_CATALOG_TO_REGISTRY` map still translates `project_ops` and `field_service` (retired keys). In production, `hr_management` has no translation and falls to Tier 3.
- **Location:** `src/agents/preview_generator/nodes/resolve_flags.py` (`_CATALOG_TO_REGISTRY`)
- **Also affected:** All 60 integration tests that pass old catalog keys as inputs

### Config Shape Mismatch (from EOD.md — being fixed in Phase 2)
- **Problem:** `generation_json.config` currently outputs generic `permission_services` and `landing_pages`.
- **What Dev C expects:** Module-specific config fields per bundle:
  - Ticketing bundle → `ticket_categories`, `default_statuses`, `queue_names`
  - HR Management bundle → `ticket_categories`, `default_statuses`, `default_priorities`, `queue_names`, `kpi_definitions`
  - Project Mgmt bundle → `task_statuses`, `task_priorities`, `milestone_statuses`, `kpi_definitions`
- **Location to fix:** `src/agents/preview_generator/nodes/emit.py` (`_build_config()`) + `src/agents/preview_generator/schemas.py` (`GenerationConfig`)
- **Reference:** `src/templates/bundles/*/app.json` — these show the actual config shape Dev C reads

---

## Next Steps (Phase 2 — in progress)

### Step 1 — Foundation
- [ ] `src/core/sanitize.py` — `sanitize_text()` utility
- [ ] `src/core/exceptions.py` — add `EditError`
- [ ] `src/api/schemas/preview.py` — add `EditRequestSchema`

### Step 2 — Catalog key fix + config shape fix
- [ ] **`resolve_flags.py`** — update `_CATALOG_TO_REGISTRY`: `{"hr_management": "hr_hub"}`, remove stale entries
- [ ] **`schemas.py`** — change `GenerationJson.config` to `dict[str, object]`, remove `GenerationConfig`, add `EditActionType` + `EditAction`
- [ ] **`emit.py`** — add `_build_config()` with per-bundle field sets
- [ ] **Update 60 existing tests** — rename catalog keys (`hr_hub`→`hr_management`, `project_ops`→`project_mgmt`, `field_service`→`ticketing`)

### Step 3 — LLM extraction
- [ ] `src/agents/preview_generator/nodes/prompts.py` — `CONTEXT_EXTRACTION_SYSTEM_PROMPT`
- [ ] `extract_context.py` — add `_get_llm()`, `_extract_context_via_llm()`, modify node to try LLM first with keyword fallback

### Step 4 — Edit flow
- [ ] `src/repositories/preview_cache_repository.py` — in-memory `PreviewOutput` cache
- [ ] `src/agents/preview_generator/edit/parse.py` — `parse_edit_instruction()`
- [ ] `src/agents/preview_generator/edit/apply.py` — `apply_edit_to_preview()` with cascading rules
- [ ] `src/api/deps.py` — add `get_preview_cache_repository()`, inject into `get_preview_flow()`
- [ ] `src/orchestrators/preview_flow.py` — cache after `run()`, add `edit()` method
- [ ] `src/api/routers/preview.py` — `POST /sessions/{id}/preview/edit` endpoint

### Step 5 — Tests
- [ ] `tests/unit/preview_generator/test_edit_parse.py`
- [ ] `tests/unit/preview_generator/test_edit_apply.py`
- [ ] `tests/integration/test_preview_edit_flow.py`
- [ ] `test_preview_generator_flow.py` — add `TestLLMFallbackBehavior` class

### Phase 3 — Production Hardening (deferred)
- [ ] Tier 2 LLM data generation for niche industries
- [ ] Per-session LLM call counter (max 3)
- [ ] Global RPM limit middleware on preview endpoints
- [ ] Full API integration testing with live Dev A + Dev C
- [ ] Load testing
- [ ] `schema_version` migration path

---

## How to Run

```bash
# Install dependencies
poetry install

# Run API server
uvicorn src.main:app --reload

# Run all tests
pytest

# Run only my tests
pytest tests/integration/test_preview_generator_flow.py tests/integration/test_dev_a_to_preview_handoff.py -v

# Lint
ruff check src/
```

**API Docs:** http://localhost:8000/docs
**ReDoc:** http://localhost:8000/docs/redoc/

---

## Bundle Reference

> Catalog keys updated 2026-03-26 (Lars) — `BundleType` enum rewritten.
> Old keys `project_ops`, `field_service`, `asset_mgmt`, `hr_hub` no longer exist as Dev A outputs.

| Catalog Key (Dev A — `BundleType`) | Registry Key | Primary Flags | Default KPIs |
|-------------------------------------|-------------|--------------|-------------|
| `project_mgmt` | `project_mgmt` | 13 + addons | on_time_delivery_rate, project_health_status, cycle_time, capacity_utilization |
| `ticketing` | `ticketing` | 13 + addons | avg_resolution_time, sla_compliance, active_work_items, cycle_time |
| `hr_management` | `hr_hub` | 21 + addons | active_headcount, attendance_rate, leave_balance_utilization, capacity_utilization |
| `finance` | — (Tier 3) | 0 | capacity_utilization, active_work_items |
| `marketing` | — (Tier 3) | 0 | capacity_utilization, active_work_items |
| `sales` | — (Tier 3) | 0 | capacity_utilization, active_work_items |
| `healthcare` | — (Tier 3) | 0 | capacity_utilization, active_work_items |
| `legal_services` | — (Tier 3) | 0 | capacity_utilization, active_work_items |
| `construction_real_estate` | — (Tier 3) | 0 | capacity_utilization, active_work_items |
| `education` | — (Tier 3) | 0 | capacity_utilization, active_work_items |
| `all_microservices` | — (Tier 3) | 0 | capacity_utilization, active_work_items |
| `generic` | — (Tier 3) | 0 | capacity_utilization, active_work_items |
