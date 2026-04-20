# EOD Updates

---

## 2026-04-15

CJ

Milestone 1 | AI Tapestry
Dashboard Service Integration — Phase 4 (Payload Integration & Logic Alignment)

### Done

- **Dashboard Module Naming Alignment** — resolved widget generation failures by ensuring all 23 industry templates use canonical module names derived from the bundle registry.
  - `src/agents/preview_generator/nodes/emit.py` — Updated `_FLAG_TO_MODULE` with full descriptive names (e.g., "HR Management", "Ticketing Tool", "Project Management") to match frontend expectations.
  - `src/agents/preview_generator/nodes/emit.py` — Modified `_derive_modules()` to automatically include the dashboard's primary bundle `display_name` (e.g., "Healthcare", "Legal Services") in the active modules list, ensuring the dashboard service recognizes these as valid modules.
  - **Bulk Template Update** — Updated **23 dashboard templates** in `dashboard_templates/` to use their respective bundle names in the `module` fields (Healthcare, Legal Services, Construction, Education, Real Estate, etc.).
  - `dashboard_templates/all_microservices_enterprise_saas.json` — Aligned with the new descriptive module naming convention.
- **Enhanced Widget Mapping (`preview_flow.py`)** — refactored dashboard enrichment to support the external generation service's native format.
  - Added support for `typeId` mapping (Number, Text, Chart, List) and positioning (`xAxis`, `yAxis`, `width`, `height`) from the external service.
  - Integrated `chartType` extraction (bar, pie, line, scatter) for dynamic widget rendering.
  - Ensured the full generation output is stored in `dummy_data_json.stores.dashboard_generation_output` for debugging.
- **Entity Relationship Mapping** — implemented a new service to handle complex entity relationships within bundles.
  - `src/agents/preview_generator/nodes/sample_data.py` — integrated `RelationshipMapper` to load from `EntityRelationshipDefinition`.
  - Added entity relationship definitions to `src/templates/bundle_registry.yaml`.
- **Integration Stability** — improved robustness of the app-generation pipeline.
  - `scripts/test_live_preview.py` — enhanced with better progress tracking and input validation.
  - Added tolerance for bundles without explicit metadata during integration.
  - Verified stability across multiple bundle tiers (`healthcare`, `legal_services`, `all_microservices`) using live integration tests.

### In Progress
- Phase 3: Production hardening and load testing.

### To Do
- Sync with Dev C on final schema validation for niche industries.

---

## 2026-04-14

CJ

Milestone 1 | AI Tapestry
Dashboard Service Integration — Phase 1

### Done

- **Dashboard Enrichment Pipeline** — integrated the external Knit dashboard generation service into the preview flow as a best-effort post-pipeline step; dashboard failures never block preview generation
  - `src/agents/preview_generator/dashboard/auth.py` — `KnitAuthService`: thread-safe Bearer token cache with configurable TTL (default 45 min), automatic lazy refresh, stale-token fallback on network failure
  - `src/agents/preview_generator/dashboard/client.py` — `DashboardClient`: POSTs personalized template to `/api/v1/dashboards/generate/`; handles timeout, network errors, 4xx/5xx, and auto-retries on 401
  - `src/agents/preview_generator/dashboard/templates.py` — `DashboardTemplateRegistry`: loads `dashboard_templates/*.json` at startup; maps bundle keys (`hr_management`, `project_mgmt`) to templates; Tier 3 bundles return None and skip the call
  - `src/agents/preview_generator/dashboard/personalizer.py` — `personalize_template()`: keyword-only mutations — company name injection, null date range defaults (last 12 months), team name substitution into chart `fields[]`
  - `src/core/config.py` — added `DASHBOARD_SERVICE_URL`, `KNIT_AUTH_URL`, `KNIT_EMAIL`, `KNIT_PASSWORD`, `DASHBOARD_AUTH_TOKEN_TTL_SECONDS`
  - `src/agents/preview_generator/service.py` — `generate()` now returns a 3-tuple `(generation_json, dummy_data_json, user_context)` so the orchestrator can pass extracted context to the personalizer without re-running extraction
  - `src/orchestrators/preview_flow.py` — `_enrich_dashboard_widgets()` wires all steps together after core pipeline; injects widgets into `dummy_data_json.stores.dashboard_widgets` and adds `stores.dashboard_meta` (id, name, url)
  - `src/api/deps.py` — added `get_knit_auth_service()`, `get_dashboard_client()`, `get_dashboard_template_registry()` DI providers; `get_preview_flow()` now injects both
  - Updated 61 integration tests for the new 3-tuple return contract — all passing

### In Progress
- (No active tasks)

### To Do
- Phase 4: Production hardening (async client, dedup, Sentry, warning surface)

---

## 2026-04-14 (cont.)

CJ

Milestone 1 | AI Tapestry
Dashboard Service Integration — Phase 3 (LLM Report Personalization)

### Done

- **LLM-assisted dashboard report personalization** — replaced static keyword substitution on the `report` field with an LLM-generated summary; keyword replacement is retained as the fallback
  - `src/agents/preview_generator/dashboard/prompts.py` — `DASHBOARD_REPORT_SYSTEM_PROMPT`: instructs the model to write a 2-3 sentence business-language description; prohibits hallucination and generic "template" language
  - `src/agents/preview_generator/dashboard/personalizer.py` — `_build_llm_human_message()`: assembles company, industry, teams, primary concern, bundle label, and last-5-user-message excerpt into the human turn; `_generate_report_via_llm()`: calls `get_openai_chat_model(temperature=ASSEMBLER_TEMPERATURE)`, returns None on no API key / empty response / any exception; `personalize_template()` now accepts optional `conversation_history` arg
  - `src/orchestrators/preview_flow.py` — `_enrich_dashboard_widgets()` accepts `conversation_history` and threads it through to `personalize_template()`
  - **Fallback chain**: no `OPENAI_API_KEY` → skip LLM → keyword substitution; LLM exception → log warning → keyword substitution; empty LLM response → keyword substitution
  - **26 new unit tests** in `tests/unit/dashboard/test_personalizer.py` — LLM happy path, whitespace stripping, no-API-key skip, exception fallback, empty-response fallback, no-history still calls LLM, `_build_llm_human_message` content assertions (company, teams, bundle, excerpt, history cap, None context)
  - **567 total tests passing** (26 new + 541 existing), 0 failures

### In Progress
- (No active tasks)

### To Do
- Phase 4: Production hardening (async client, dedup, Sentry, warning surface)

---

## 2026-04-14 (cont.)

CJ

Milestone 1 | AI Tapestry
Dashboard Service Integration — Phase 2 (Unit Tests)

### Done

- **68 unit tests for the dashboard package** — full coverage of all four new modules with no mocking shortcuts
  - `tests/unit/dashboard/test_auth.py` (25 tests) — token caching within TTL, refresh after expiry, `invalidate()` forces re-auth, stale-token fallback on network/HTTP errors, first-call failure returns None, `_parse_token()` tested across all field name variants (`token`, `access_token`, `key`, `data.*`) and bad shapes
  - `tests/unit/dashboard/test_client.py` (13 tests) — success path, correct URL and Bearer header, no-token short-circuit, 401 → invalidate → retry succeeds, double-401 returns None, 500/404 return None, `success=false` returns None, timeout / connect / read errors return None, trailing-slash base URL normalisation
  - `tests/unit/dashboard/test_templates.py` (14 tests) — `hr_management`, `hr_hub` alias, `project_mgmt` resolve correctly; Tier 3 / unknown bundles return None; `get()` returns deep copies (mutations don't affect cache); missing file logs warning + returns None; invalid JSON logs warning + returns None; `supported_bundles()` includes known keys only
  - `tests/unit/dashboard/test_personalizer.py` (16 tests) — original template not mutated; "Template" replaced by company name; company appended when no placeholder; null `date_from`/`date_to` filled with last-12-months defaults; existing dates not overwritten; non-`data_config` widgets unaffected; empty `fields[]` filled with team names (capped at 6); non-empty fields not replaced; full no-op when `user_context=None`
  - **541 total tests passing** (68 new + 473 existing), 0 failures, 1.6s for the dashboard suite

### In Progress
- (No active tasks)

### To Do
- Phase 4: Production hardening (async client, dedup, Sentry, warning surface)

---

## 2026-04-13

CJ

Milestone 1 | AI Tapestry
Develop Bundle Classifier and Confidence Scorer

### Done

- **All Modules Activated Regardless of Bundle (`resolve_flags.py`)** — changed flag resolution so all 69 feature flags are always `isEnabled: true` for every bundle, regardless of industry or tier
  - Removed tier-1 gating and per-bundle flag accumulation logic — function now emits a flat `{flag_name: True}` dict for the full catalog
  - `permission_services` and `landing_pages` still resolve from the bundle registry as before — bundle identity still drives config and dummy data stores
  - Unknown/Tier 3 bundles now also receive all 69 flags enabled (previously returned all false)
  - `generation_json.modules` now always contains all 10 modules: `Projects, Tickets, HRHub, Weaves, Dashboard, KPI, Calendar, Chat, AIToolkit, Rewards`
  - Updated 5 test assertions in `test_preview_generator_flow.py`: flipped cross-bundle `False` checks to `True`, renamed `test_no_flags_enabled` → `test_all_flags_enabled` (expects 69), renamed `test_modules_empty` → `test_all_modules_present` (expects 10)
  - 46 integration tests passing

### In Progress
- (No active tasks)

### To Do
- Commit and push current branch
- Phase 3: Production hardening, load testing, niche industry Tier 2 data generation

---

## 2026-04-10

CJ

Milestone 1 | AI Tapestry
Develop Bundle Classifier and Confidence Scorer

### Done

- **Preview Payload Alignment (`emit.py`)** — aligned output payloads with frontend contract on branch `fix/SS1-T152-02-registry-alignment`
  - `generation_json.bundle_key` and `dummy_data_json.bundle_key` now emit the render key (e.g. `hr_hub`) instead of the catalog key (`hr_management`)
  - `config.kpi_definitions` changed from `list[str]` to `list[object]` — each entry now includes `key`, `label`, and `unit` fields
  - `_BUNDLE_CONFIG_FIELDS` cleaned up to render keys only (`hr_hub`, `project_mgmt`, `ticketing`) — removed stale `hr_management` duplicate entry
  - Refactored `_build_config()` signature from 6 positional args to `(registry_key, state)` — resolves pylint `too-many-arguments` warnings; pylint now 10.00/10
  - Updated test assertion for `TestHRHub.test_generation_json_structure` to expect `hr_hub` as `bundle_key`
  - Applied `black` formatting to `test_preview_generator_flow.py`
  - All linters clean: mypy, flake8, ruff, black, pylint 10.00/10
  - 61 integration tests passing

### In Progress
- (No active tasks)

### To Do
- Commit and push current branch (`fix/SS1-T152-02-registry-alignment`)
- Phase 3: Production hardening, load testing, niche industry Tier 2 data generation

---

## 2026-04-09

CJ

Milestone 1 | AI Tapestry
Develop Bundle Classifier and Confidence Scorer

### Done
- **`test_preview_edit_flow.py` (35 tests)** — End-to-end generate → edit cycle for all Tier 1 bundles
  - HR Management: company extraction, store names (tickets/queues), KPI presence, then edit to remove a module and verify cascading cleanup
  - Project Mgmt: store names (tasks/milestones), flag states, then edit to add/remove modules
  - Ticketing: store names, bundle key in response, then edit instruction round-trip
  - Contract tests: schema fields present, warning propagation, unrecognised instructions return graceful warning
- **`test_classifier_to_preview_flow.py` (34 tests)** — AI Bundle Classifier output flowing into the preview generator
  - Scenario A (Classifier → Preview): `ExtractionResult` with `PersonalizationSignals` and `ClassificationSignals` passed as `accumulated_extraction`; verifies company name, KPI signal boosts, correct store names, and flag states per bundle across all tiers (Tier 1: hr_management, project_mgmt, ticketing; Tier 3: finance, sales, healthcare, etc.)
  - Scenario B (Generate Now / Early Preview): preselected bundle key at session start, classifier's `suggestions[]` confidence score used mid-conversation, and no-bundle fallback to `all_microservices` — all via `/preview/early`
- **Fixed 7 failing tests** — stale `all_microservices` render key assertion in bundle catalog; `_seed_session` missing default conversation history causing 400s; `latest_classification` shape mismatch (`top_bundle_key` vs `suggestions[]`)
- **Fixed `catalog/bundle_catalog.py`** — `_add_legacy_aliases()` was missing `render_key` when building the `hr_hub` alias, causing `ValidationError` on catalog load
- **96% test coverage** on the preview generator — 463 tests, all passing

### In Progress
- (No active tasks)

### To Do
- Commit and push current branch (`fix/SS1-T152-02-registry-alignment`)
- Phase 3: Production hardening, load testing, niche industry Tier 2 data generation

---

## 2026-04-08

CJ

Meetings
- Async review with Lars on bundle registry and confidence guard feedback

Milestone 1 | AI Tapestry
Develop Bundle Classifier and Confidence Scorer

Task: Bundle Config Enrichment
Description: Preview output was emitting generic placeholder config fields regardless of bundle. Each bundle now produces the exact config shape Dev C expects, derived from the actual generated sample data.
Done:
- Refactored `_build_config()` to derive ticket statuses, queue names, task priorities, and KPI definitions from real sample data per bundle
- Each Tier 1 bundle (ticketing, hr_management, project_mgmt) now outputs its own distinct config fields
- Updated unit tests to cover all three bundle config variants

Task: Bundle Registry Alignment
Description: Internal bundle naming was misaligned — the pipeline used a legacy `hr_hub` key that didn't match what Dev A sends, causing incorrect behavior and a broken translation layer.
Done:
- Renamed `hr_hub` to `hr_management` across the registry, store schema, and config mappings so the catalog key flows through without any translation
- Removed the catalog-to-render-key translation function entirely — no longer needed
- Fixed `all_microservices` render key which was incorrectly mapped to the HR bundle
- Restored the confirmed preview endpoint that was accidentally dropped in a prior commit
- All 141 preview generator tests passing

Task: Lars Review Fixes
Description: Addressed feedback from Lars covering keyword extraction, early preview confidence handling, and session state.
Done:
- Migrated all hardcoded keyword lists out of the code and into the bundle registry YAML so they're driven by config
- Early preview now checks the classifier's confidence score before using its bundle guess — low-confidence results fall back to the default
- Session now carries the full suggestions list with confidence scores so the guard has the data it needs
- Fixed Tier 2 extraction path to include preselected intent in key phrases

---

## 2026-04-07

### Done

- **T139 — Preview Data Population Logic (started):** Began implementing `sample_data.py` enhancements — added industry-aware generation for employees, projects, tickets, and weaves. Refactored `_dept_pool()` to accept `user_context.teams` and `branch_names` so department pools reflect real conversation signals before falling back to bundle defaults.

### In Progress

- **`emit.py` Config Enrichment:** Started `_build_config()` refactor to produce per-bundle config fields from generated sample data instead of generic placeholders. Ticketing bundle shape drafted; HR and project_mgmt in progress.

### To Do

- Finish `_build_config()` for all three Tier 1 bundles.
- Write unit tests for `_dept_pool()` overrides and all config variants.
- **Branch 2 (T138):** KPI signal-boost unit tests still pending.
- **Phase 3:** Production hardening deferred.

---

## 2026-04-01

### Done

- **Sequential Push & MR Preparation:** Completed the sequential push of 5 atomic branches (`SS1-T137` to `SS1-T138`) to origin. This organized the day's work into logical review units: Registry Fixes, Pipeline Threading, 3-Tier Extraction, Data Population Enhancements, and the Final Edit Flow.
- **Final Integration & Verification:** Ran final exhaustive regression tests (364+ pass) across the segmented branches to ensure all internal component contracts were maintained throughout the decomposition process.
- **Preview Edit Sub-graph Finalization:** Finalized the stateful applier and parser logic for natural-language edits, ensuring cascading effects (like metric-cleanup on module removal) are correctly triggered via the new endpoints.

### In Progress

- (No active tasks)

### To Do

- **Phase 3:** Production hardening, load testing, and niche industry data generation.
- **Phase 4:** Merge the `SS1-T138` series into the main preview development trunk after review.

---

## 2026-03-31

### Done

- **Preview Edit Flow (Phase 2 - Step 4):** Implemented the natural-language edit sub-graph. Built `parse.py` (instruction parser for "remove chat", "add KPI") and `apply.py` (stateful applier with cascading removal of related stores and metrics). Added `POST /sessions/{id}/preview/edit` stateless endpoint.
- **TDD Implementation:** Applied a Test-Driven Development approach for the edit flow and data population logic, adding 50 new unit and integration tests.
- **Three-Tier User Context Extraction:** Implemented high-performance Tier 1 extraction (mapping `ExtractionResult` from Dev A direct to `UserContext`) to skip redundant LLM calls, with Tier 2 keyword fallbacks.
- **Enhanced Data Population:** Updated `kpi.py` with signal-boosting (prioritizing metrics from classification signals) and `sample_data.py` with department-aware pooling from `UserContext` and `branch_names`.
- **Bundle Registry & Template Fixes:** Resolved `BundleRegistryValidationError` by correcting `template_dir` paths and stripping redundant fields from Tier 1 templates.

### In Progress

- (No active tasks)

### To Do

- **Phase 3:** Align `generation_json.config` with final frontend field requirements for edge-case bundles.

---

## 2026-03-30

### Done

- Created `SYSTEM_OVERVIEW.md` providing a high-level summary of the AI Architect pipeline, core components, and project status.
- Integrated `Dashboard Template Preview.pdf` content: Added 50+ new KPI metrics to `registry.py` and updated/added 10 industry bundles (Marketing, Sales, Healthcare, etc.).
- Aligned `generation_json.config` and `dummy_data_json.stores` in `emit.py` with the specific requirements of the new industry bundles.
- Updated `resolve_flags.py` to map new catalog keys (`legal_services`, `construction_real_estate`) to their respective registry keys.
- **Phase 2 - Step 3**: Completed the prompts and LLM integration in `extract_context.py` with the keyword-based fallback system.

### In Progress

- (No active tasks)

### To Do

- **Phase 2 - Step 4**: Implement `edit/parse.py`, `edit/apply.py`, and `POST /sessions/{id}/preview/edit` endpoint.
- **Phase 3**: Production hardening, load testing, and niche industry data generation.

---

## 2026-03-24

### Done

- Implemented the full Phase 1 LangGraph pipeline (7 nodes, zero LLM calls) — context extraction, flag resolution, data tier routing, sample data generation, KPI assembly, validation, and output emission.
- Fixed all integration gaps between Dev A's conversation flow and the preview generator: bundle key translation, tier routing, store name contract, and the blocking bug where `selected_bundle_key` was never persisted to the session after `process_turn`.
- Added 60 integration tests (45 pipeline-level + 15 API end-to-end) covering all 5 catalog bundles, store name correctness, flag states, and the full `POST /sessions → /reply → /confirm → /preview` HTTP chain. All pass with no mocking required.

### In Progress

- `generation_json.config` shape is misaligned — our `emit.py` outputs generic `permission_services` and `landing_pages` but `app.json` templates expect module-specific config (`ticket_categories`, `default_statuses`, `queue_names`, `kpi_definitions`). Shape audit underway.

### To Do

- **Fix 3:** Align `generation_json.config` with the actual `app.json` template shape per bundle.
- **Phase 2:** Replace keyword-based `extract_context.py` with a structured LLM call; keyword logic becomes fallback.
- **Phase 2:** Add Tier 2 LLM data generation for niche / unrecognised industries.
- **Phase 2:** Implement `edit/parse.py`, `edit/apply.py`, and `POST /sessions/{id}/preview/edit` endpoint.
