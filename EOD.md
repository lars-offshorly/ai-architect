# EOD Updates

> **Format:** High level, short (2–3 sentences per item). Group into Done / In Progress / To Do.

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
