# Preview Generator — Changelog

---

## EOD Update — 2026-03-24

> Branch: `internal-dev`
> Focus: End-to-end integration between Dev A's conversation flow and the preview generator pipeline

### Bug Fixes

- **Bundle key translation gap** — `resolve_flags.py` was doing a direct lookup of Dev A's catalog keys (`project_ops`, `field_service`) against `BUNDLE_REGISTRY`, which uses different keys (`project_mgmt`, `ticketing`). Only `hr_hub` was resolving correctly; all others silently fell through to Tier 3. Added a `_CATALOG_TO_REGISTRY` translation table at the top of `resolve_flags.py` to map catalog keys to registry keys before any lookup.

- **Tier routing broken for translated bundles** — `data_tier.py` was checking `state.bundle_key` (the original catalog key) against `BUNDLE_REGISTRY` to decide Tier 1 vs Tier 3. Since catalog keys don't exist in the registry, every translated bundle (`project_ops`, `field_service`) was incorrectly routed to Tier 3 (generic fallback), even after the flag resolution step had translated them. Fixed to use `state.resolved_bundle_ids[0]` (the post-translation registry key) for the tier check.

- **Wrong store names in `dummy_data_json`** — `emit.py` was hardcoding `tasks` and `tickets` regardless of bundle, so `hr_hub` and `field_service` would get `tasks` instead of `tickets`, and `project_ops` would get `tickets` instead of `tasks`. Added a `_STORE_SCHEMA` mapping (keyed by registry bundle) that encodes the correct frontend store names (`primary`, `secondary`, `weaves`) per bundle. The `_build_stores()` helper uses this schema to populate the stores dict.

- **`session.selected_bundle_key` never persisted** — `ConversationFlow.process_turn()` returns `bundle_key` in the result dict when a bundle is identified during conversation, but both `start_session` and `reply_to_session` in `session.py` were discarding it. This caused `POST /sessions/{id}/preview` to always return `400 — session not confirmed` even after a valid `/confirm` call. Added two lines in each handler to write `bundle_key` to the session object and save it.

- **Stale import breaking `api.deps`** — `src/api/__init__.py` had a leftover `from .app import create_app` referencing an old `api/app.py` that imported `Database` and `pinecone_client` from `core`. Those no longer exist, so any import of `api.deps` (including the test suite) was failing with `ImportError`. Cleared the file to only `from __future__ import annotations`.

- **Plural keyword forms not detected in context extraction** — `_AGILE_KEYWORDS` in `extract_context.py` had `"sprint"` but conversations naturally use `"sprints"`, `"standups"`, `"backlogs"`, `"iterations"`. Added the plural and common variant forms so methodology detection works on realistic input.

### Refactors

- **Reduced cognitive complexity in `resolve_flags.py`** — The main `resolve_bundles_to_flags` function had a cognitive complexity score of 19 (SonarQube limit: 15). Extracted two helper functions: `_collect_bundle_ids()` to gather primary + addon bundle IDs from the registry, and `_accumulate()` to merge flags, services, and landing pages across all bundle IDs.

### Tests Added

- **`tests/integration/test_preview_generator_flow.py`** — 45 tests that call `PreviewGeneratorService.generate()` directly against the full LangGraph pipeline. No mocking required (Phase 1 has zero LLM calls). Covers:
  - All 5 catalog bundle keys: `hr_hub`, `project_ops`, `field_service`, `asset_mgmt`, `generic`
  - Correct store names per bundle (`tickets/queues`, `tasks/milestones`, `items/projects`)
  - Feature flag presence and enabled state per bundle
  - KPI metric content and structure
  - Company name and people extraction from conversation history
  - Graceful handling of empty conversation history
  - Parametrized coverage for flag shape and primary/secondary store names

- **`tests/integration/test_dev_a_to_preview_handoff.py`** — 15 tests covering the HTTP API layer end-to-end. Two layers:
  - **Layer 1 (12 tests)**: Pre-seeds `SessionRepository` and `ConversationRepository` to mirror Dev A's confirmed session state, then calls `POST /sessions/{id}/preview` directly. Validates `200` responses, correct `bundle_key`, `display_name`, `generation_json`, `dummy_data_json` store names, and error handling (`400` for unconfirmed, `404` for missing session).
  - **Layer 2 (3 tests)**: Drives the full `POST /sessions → /reply → /confirm → /preview` HTTP sequence using `FastAPI.dependency_overrides` to inject a mock `ConversationFlow` (avoids triggering `InterpreterService` which requires an OpenAI key). Validates that `selected_bundle_key` is persisted at each turn and that the full chain produces `200` on `/preview`.

- **`conftest.py`** (project root) — Created to add `src/` to `sys.path` at test collection time, allowing all `src/` modules (`agents`, `api`, `core`, etc.) to be imported without install.

### Test Results

```
60 passed in ~3s  (45 pipeline + 15 API integration)
```

---

## [Unreleased] — Phase 1 Foundation

> Branch: `internal-dev`
> Scope: `src/agents/preview_generator/`

---

### Added

#### `src/agents/preview_generator/bundles/registry.py` _(new file)_

Single source of truth for all bundle and feature flag data. Replaces the disk-template lookup in `TemplateFetcher`.

- **`ALL_FEATURE_FLAGS: list[dict]`** — 69 entries seeded verbatim from `docs/api-mocks.json` (`orchestration.GET./feature_flags/all.response.results`). All `isEnabled` values set to `False` by default. Shape: `{id, name, description, isEnabled, module}`.
- **`_FLAG_INDEX: dict[str, dict]`** — internal fast-lookup index keyed by flag name; same object references as `ALL_FEATURE_FLAGS` (no copy).
- **`BUNDLE_REGISTRY: dict[str, dict]`** — 9 bundle definitions:
  - Core bundles: `project_mgmt`, `ticketing`, `hr_hub`, `weaves`
  - Addon bundles: `chat`, `video_call`, `smart_vault`, `announcements`, `calendar`
  - Each entry carries: `flags`, `permission_services`, `landing_pages`, `compatible_addons`, `default_metrics`
- **`METRICS_CATALOG: dict[str, dict]`** — 17 KPI metric definitions keyed by slug. Grouped into: delivery performance, operational efficiency, team productivity, HR metrics. Shape: `{key, label, type, source_service}`.
- **`get_flag_snapshot() -> list[dict]`** — returns a deep copy of `ALL_FEATURE_FLAGS` with all flags disabled. Callers mutate this copy; the source list is never modified.

---

#### `src/agents/preview_generator/schemas.py` _(new file)_

Internal pipeline models. Never serialized in API requests or responses — used exclusively as working state inside the LangGraph pipeline.

Rationale for a separate schema vs reusing `ExtractedInfo` (Dev A): `ExtractedInfo` carries flat lists (`role_names: list[str]`). The sample data generator needs structured objects — `work_items[].work_type` to drive project naming strategy, and `role + department` paired per person for employee records.

- **`PersonDetail`** — a person mentioned in conversation: `name`, `role`, `department`, `is_user: bool`
- **`TeamDetail`** — a team or department: `name`, `size`, `function`
- **`WorkItemDetail`** — a type of work item: `name`, `work_type` (`sprint | litigation | waterfall | support_request`), `has_deadlines`, `methodology`
- **`UserContext`** — full extracted business context produced by `extract_user_context` and consumed by `generate_sample_data` and `build_kpi_metrics`: `company_name`, `company_size`, `industry_detail`, `people`, `teams`, `work_items`, `has_remote_teams`, `has_clients`, `work_methodology`, `primary_concern`, `key_phrases`

---

#### `src/agents/preview_generator/state.py` _(new file)_

LangGraph working memory for the 7-node preview pipeline. A single `PreviewGeneratorState` instance is passed through all nodes; each node returns a partial dict that updates only its fields.

Fields by lifecycle stage:

| Stage | Fields set |
|---|---|
| Graph entry (never mutated) | `session_id`, `bundle_key`, `conversation_history` |
| `extract_user_context` | `user_context` |
| `resolve_bundles_to_flags` | `resolved_bundle_ids`, `feature_flags`, `permission_services`, `landing_pages` |
| `select_data_tier` | `data_tier` |
| `generate_sample_data` | `sample_employees`, `sample_projects`, `sample_tickets`, `sample_weaves` |
| `build_kpi_metrics` | `kpi_metrics` |
| `validate_schema` | `schema_valid`, `validation_errors`, `retry_count` |
| `emit_preview` | `output` |

`max_retries: int = 2` — controls the retry loop from `validate_schema` back to `resolve_bundles_to_flags`.

---

### Changed

#### `src/agents/preview_generator/__init__.py`

- Added public exports for all data classes and state:
  - `PersonDetail`, `TeamDetail`, `WorkItemDetail`, `UserContext` (from `schemas.py`)
  - `PreviewGeneratorState` (from `state.py`)
- `PreviewGeneratorService` export retained (service rewrite is pending)

---

### Pending (Phase 1 — not yet implemented)

The following are planned but not yet on disk:

| File | Description |
|---|---|
| `nodes/extract_context.py` | Keyword-based `UserContext` extraction from `conversation_history` |
| `nodes/resolve_flags.py` | Deterministic bundle → feature flags resolution using `BUNDLE_REGISTRY` |
| `nodes/data_tier.py` | Tier 1 (known bundle) vs Tier 3 (fallback) selection |
| `nodes/sample_data.py` | Programmatic employee / project / ticket / weave generation |
| `nodes/kpi.py` | KPI assembly from `METRICS_CATALOG` |
| `nodes/validate.py` | Business rule validation with retry routing |
| `nodes/emit.py` | Assembles `generation_json` (Knit API shape) + `dummy_data_json` (legacy stores) |
| `pipeline.py` | LangGraph `StateGraph` wiring all 7 nodes |
| `service.py` | Rewrite — removes `TemplateRepository` dependency, invokes compiled graph |

Files to be deleted when `service.py` is rewritten:

| File | Replaced by |
|---|---|
| `fetcher.py` | `bundles/registry.py` + `nodes/resolve_flags.py` |
| `modifier.py` | `nodes/sample_data.py` |
| `dummy_data.py` | `nodes/sample_data.py` |
| `validators.py` | `nodes/validate.py` |

Files outside `preview_generator/` to be updated in Phase 1:

| File | Change |
|---|---|
| `src/api/deps.py` | Drop `TemplateRepository` from `get_preview_generator_service()` |
| `src/orchestrators/preview_flow.py` | Accept `conversation_history`; bypass `AppGeneratorService`; build `AppPayload` directly |
| `src/api/routers/preview.py` | Pass `conversation_history` from `ConversationRepository` into `PreviewFlow.run()` |

---

### Pending (Phase 2 — not yet started)

| File | Description |
|---|---|
| `nodes/extract_context.py` (upgrade) | Replace keyword scan with structured LLM call; keyword logic becomes fallback |
| `nodes/sample_data.py` (upgrade) | Add Tier 2 LLM data generation for niche industries |
| `edit/parse.py` | Parse plain-English edit instruction into typed `EditAction` |
| `edit/apply.py` | Apply `EditAction` to current Knit JSON; cascading rules for remove/add module |
| `src/api/routers/preview.py` (new endpoint) | `POST /sessions/{id}/preview/edit` |
