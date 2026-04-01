# Feature: Generate Preview Configuration

## 1. Feature Overview

**Feature Name:** Generate Preview Configuration

**Short Description:** A 7-node LangGraph pipeline that converts a confirmed bundle key and conversation history into a complete Knit workspace JSON with personalized sample data — fully deterministic in Phase 1, with no LLM calls.

**Business Purpose:** Allow users to see an interactive preview of their configured workspace before committing to provisioning. The preview must feel personalized to their industry, team structure, and work style so they can validate the AI's understanding and correct it before real resources are created.

**Problem It Solves:** Without a preview step, users commit to workspace creation blindly — they cannot verify that the AI selected the right modules, populated relevant sample data, or understood their industry terminology. The preview generator bridges the gap between classification (Component 1) and provisioning (Component 3) by producing a realistic, inspectable workspace configuration.

---

## 2. Scope

### In Scope

- **Full pipeline execution** — 7 nodes in sequence: `extract_user_context` → `resolve_bundles_to_flags` → `select_data_tier` → `generate_sample_data` → `build_kpi_metrics` → `validate_schema` → `emit_preview`.
- **Validation retry loop** — if `validate_schema` fails, the pipeline retries from `resolve_bundles_to_flags` up to 2 times before emitting best-effort output.
- **Bundle key translation** — catalog keys from Dev A (`project_ops`, `field_service`) are translated to registry keys (`project_mgmt`, `ticketing`) via `_CATALOG_TO_REGISTRY`.
- **Tier 1 and Tier 3 data generation** — known bundles get personalized data; unknown bundles get generic fallback data.
- **Service layer** — `PreviewGeneratorService.generate()` wraps pipeline invocation and returns `(generation_json, dummy_data_json)`.
- **Orchestration integration** — `PreviewFlow.run()` calls the service, assembles `AppPayload`, and returns the HTTP response model.

### Out of Scope

- LLM-based context extraction (Phase 2 upgrade to `extract_user_context`).
- Tier 2 LLM-generated sample data for niche industries (Phase 2).
- Edit sub-graph for user modifications to the preview (Phase 2).
- Rate limiting and per-session LLM call counters (Phase 2 security hardening).
- Real-time streaming of pipeline progress to the frontend.

### Limitations

- Keyword-based context extraction has limited accuracy — it relies on pattern matching rather than semantic understanding of conversation content.
- The pipeline is synchronous and stateless between invocations — there is no caching of intermediate results across requests for the same session.
- Tier 2 is defined but not implemented; any bundle that partially matches falls through to Tier 3.

---

## 3. Business Rules

1. **Pipeline must complete without LLM calls in Phase 1.** Every node is deterministic. No network calls, no model inference, no external service dependencies.

2. **Bundle key translation is mandatory before registry lookup.** Dev A's catalog uses keys like `project_ops` and `field_service`; the preview generator registry uses `project_mgmt` and `ticketing`. The `_CATALOG_TO_REGISTRY` map in `resolve_flags.py` performs this translation. Unrecognized keys pass through untranslated and resolve to Tier 3.

3. **Compatible addons are included automatically.** When a primary bundle is resolved, all entries in its `compatible_addons` list are recursively resolved — their flags, services, and landing pages are merged into the output.

4. **Retry budget is 2.** If `validate_schema` fails, the pipeline routes back to `resolve_bundles_to_flags` and re-executes the downstream nodes. After 2 retries, the pipeline emits whatever data it has (best-effort).

5. **No code path may produce zero sample records.** Even Tier 3 (generic fallback) must generate minimum placeholder data: 8 employees, 5 projects, 6 tickets.

6. **Conversation history is read-only.** The pipeline never modifies, truncates, or filters the conversation history. All turns (user and assistant) are scanned for context signals.

7. **State updates are partial.** Each node returns only the fields it owns. The LangGraph runtime merges these into the shared `PreviewGeneratorState`. No node may overwrite another node's fields.

---

## 4. User Flow / Workflow

1. **User completes conversation** with the AI classifier (Dev A's Component 1), which identifies their industry, bundles, and work style.
2. **User confirms bundle selection** via `POST /sessions/{id}/confirm`, which sets `session.confirmed = True` and persists `selected_bundle_key`.
3. **Frontend requests preview** via `POST /sessions/{id}/preview`.
4. **Router validates session** — checks existence, confirmation status, and bundle key presence.
5. **Router assembles conversation history** from `ConversationRepository.get_messages()` and transforms to `[{role, content}]` dicts.
6. **PreviewFlow.run()** is called with `session_id`, `bundle_key`, and `conversation_history`.
7. **PreviewGeneratorService.generate()** creates initial `PreviewGeneratorState` and invokes the compiled LangGraph.
8. **Pipeline executes 7 nodes** in sequence:
   - `extract_user_context` — scans conversation for company name, industry, teams, roles, work types.
   - `resolve_bundles_to_flags` — translates bundle key, enables flags, includes addons.
   - `select_data_tier` — determines Tier 1 (known) or Tier 3 (fallback).
   - `generate_sample_data` — produces employees, projects, tickets, weaves with industry-appropriate names and roles.
   - `build_kpi_metrics` — assembles KPI widgets from bundle defaults and conversation signals.
   - `validate_schema` — checks minimum data requirements; retries if needed.
   - `emit_preview` — assembles `generation_json` and `dummy_data_json`.
9. **Service validates output** against `PreviewOutput` schema and returns the two dicts.
10. **PreviewFlow wraps in AppPayload** with display name and module list.
11. **Router returns `AppPayloadResponseSchema`** (HTTP 200) to the frontend.
12. **Frontend renders the interactive preview** using the feature flags, module list, and sample data stores.

---

## 5. Acceptance Criteria

- [ ] `POST /sessions/{id}/preview` returns HTTP 200 with valid `generation_json` and `dummy_data_json` for all 5 catalog bundle keys: `hr_hub`, `project_ops`, `field_service`, `asset_mgmt`, `generic`.
- [ ] Catalog key translation works: `project_ops` resolves to `project_mgmt` flags; `field_service` resolves to `ticketing` flags.
- [ ] Compatible addons are automatically included — e.g., `project_mgmt` includes `chat`, `video_call`, `smart_vault`, `announcements` flags.
- [ ] Conversation history containing company name, team names, and role mentions produces personalized sample data (not generic placeholders).
- [ ] Empty conversation history produces valid output with generic defaults (Tier 3 behavior).
- [ ] Validation retry loop executes: if a node produces insufficient data, the pipeline retries up to 2 times before emitting best-effort output.
- [ ] Pipeline completes in under 3 seconds with zero network calls.
- [ ] `POST /sessions/{id}/preview` returns HTTP 400 if session is not confirmed or has no bundle key.
- [ ] `POST /sessions/{id}/preview` returns HTTP 404 if session does not exist.
- [ ] All 60 integration tests pass (45 pipeline + 15 API).

---

## 6. Security Considerations

- **No LLM calls in Phase 1.** The pipeline is fully deterministic, eliminating prompt injection risk, LLM latency variability, and API key exposure during preview generation.
- **Session isolation.** Each pipeline invocation creates a fresh `PreviewGeneratorState`. No state is shared between sessions or persisted beyond the request lifecycle.
- **Input validation at the router.** The preview endpoint validates session existence and confirmation status before invoking the pipeline. Unauthenticated or unconfirmed sessions are rejected with appropriate HTTP error codes.
- **Read-only conversation access.** The pipeline reads conversation history but never writes to it, preventing data corruption in the upstream conversation store.
- **Immutable registry data.** `ALL_FEATURE_FLAGS` and `BUNDLE_REGISTRY` are module-level constants. `get_flag_snapshot()` returns deep copies so pipeline mutations cannot affect other requests.
- **No user input in structural fields.** Feature flag names, module names, permission services, and landing page IDs are all sourced from static constants. User-provided text only appears in sample data fields (employee names, company name) which are display-only.
