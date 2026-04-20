# Feature: Preview Schema Definition

## 1. Feature Overview

**Feature Name:** Preview Schema Definition

**Short Description:** Defines the canonical JSON output structure that the preview generator pipeline produces, establishing the contract between the AI pipeline, frontend renderer, and downstream workspace provisioner.

**Business Purpose:** Provide a single, well-defined data contract so the frontend can render an interactive workspace preview and the App Generator (Component 3) can provision a real workspace from the same payload — without ambiguity or ad-hoc field negotiation between teams.

**Problem It Solves:** Without a formal schema, each component (classifier, preview generator, frontend, provisioner) would interpret the preview payload differently, leading to rendering bugs, missing data, and integration failures. The schema definition eliminates this by codifying every field, its type, and its purpose.

---

## 2. Scope

### In Scope

- **`GenerationJson` schema** — the Knit workspace configuration payload containing feature flags, active modules, permission services, and landing page configuration.
- **`DummyDataJson` schema** — the sample data payload containing employees, projects/tasks, tickets, weaves, KPIs, and dashboard widgets keyed by frontend store names.
- **`PreviewOutput` schema** — the combined wrapper that pairs `generation_json` and `dummy_data_json` as a single pipeline output.
- **`PreviewGeneratorState` schema** — the LangGraph working-memory contract that each pipeline node reads from and writes to.
- **Supporting schemas** — `UserContext`, `PersonDetail`, `TeamDetail`, `WorkItemDetail`, `KpiMetric` used internally by nodes and serialized into the output.
- **Feature flag envelope** — the 69-entry feature flag array with `{id, name, description, isEnabled, module}` shape, seeded from `docs/api-mocks.json`.
- **Store name mapping** — per-bundle mapping of internal data (sample_tickets, sample_projects) to frontend store keys (tasks, milestones, tickets, queues, weaves).

### Out of Scope

- JSON Schema validation at the HTTP boundary (Phase 3 concern).
- OpenAPI / Swagger spec generation for the preview endpoints.
- Schema versioning or migration tooling beyond the `schema_version` field.
- Frontend TypeScript type definitions — these are owned by the frontend team and derived from this contract.

### Limitations

- The `schema_version` field is currently hardcoded to `"1.0"` and has no automated migration path.
- `_preview_metadata` (described in the JSON Preview Plan) is not implemented in Phase 1; metadata fields are distributed across `generation_json` and `dummy_data_json` instead.

---

## 3. Business Rules

1. **`generation_json` must always contain a complete feature flag array.** All 69 flags must be present in the output, each with an explicit `isEnabled` value. Omitting a flag is not permitted — the frontend relies on the full set for conditional rendering.

2. **`dummy_data_json.stores` keys must match the frontend store names for the resolved bundle.** The mapping is:
   - `project_mgmt` → `tasks` (primary), `milestones` (secondary)
   - `ticketing` → `tickets` (primary), `queues` (secondary)
   - `hr_hub` → `tickets` (primary), `queues` (secondary)
   - `weaves` → `weaves`
   - KPIs and dashboard widgets are always present regardless of bundle.

3. **Every KPI metric must include a `sample_value` of the correct type for its metric type** (percentage → float, count → int, duration → float, status → string, ratio → float).

4. **The `bundle_key` field must appear in both `generation_json` and `dummy_data_json`** to allow independent consumption of either payload.

5. **`generation_json.modules` must be derived from enabled flags only** — no module name may appear unless its corresponding feature flag has `isEnabled: true`.

6. **Employee records must include at minimum:** `id`, `name`, `role`, `department`, `email`, `is_active`.

7. **Ticket records must include at minimum:** `id`, `title`, `type`, `status`, `priority`, `requester`, `assignee`, `created_at`.

8. **Project records must include at minimum:** `id`, `name`, `status`, `lead`, `team_size`, `start_date`, `due_date`, `completion_pct`.

---

## 4. User Flow / Workflow

1. **Pipeline receives inputs** — `session_id`, `bundle_key`, and `conversation_history` are loaded into `PreviewGeneratorState`.
2. **Nodes populate state fields** — each of the 7 pipeline nodes reads from state, performs its work, and returns a partial dict that updates specific state fields.
3. **Validation checks schema compliance** — the `validate_schema` node verifies that the populated state meets minimum data requirements (flags resolved, employees present, KPIs present).
4. **Emit node assembles output** — `emit_preview` reads the full state and constructs both `generation_json` and `dummy_data_json` by:
   - Building the flag list from the `feature_flags` dict and `ALL_FEATURE_FLAGS` metadata.
   - Deriving active module names from enabled flags.
   - Mapping sample data arrays to the correct frontend store keys using `_STORE_SCHEMA`.
   - Serializing KPI metrics with sample values.
5. **Service layer unpacks output** — `PreviewGeneratorService.generate()` validates the output against `PreviewOutput` and returns the two dicts as a tuple.
6. **Orchestrator wraps in AppPayload** — `PreviewFlow.run()` wraps the dicts into an `AppPayload` with display name and module list for the HTTP response.

---

## 5. Acceptance Criteria

- [ ] `GenerationJson` contains `schema_version`, `bundle_key`, `feature_flags` (list of 69 dicts), `modules` (list of strings), and `config` (with `permission_services` and `landing_pages`).
- [ ] `DummyDataJson` contains `bundle_key`, `session_id`, `company_name`, and `stores` dict with correct keys per bundle.
- [ ] Each feature flag dict has exactly the keys: `id` (int), `name` (str), `description` (str), `isEnabled` (bool), `module` (str).
- [ ] `modules` list only includes display names for flags where `isEnabled` is `true`.
- [ ] Store keys match the `_STORE_SCHEMA` mapping for the given bundle — no hardcoded `tasks` or `tickets` regardless of bundle.
- [ ] KPI entries in `stores.kpis` each have `key`, `label`, `type`, `source_service`, and `sample_value`.
- [ ] `PreviewOutput.model_validate()` succeeds on every pipeline output without raising `ValidationError`.
- [ ] Changing a bundle key produces a structurally different output (different flags enabled, different store keys, different KPI metrics).
- [ ] Tier 3 (fallback) output still conforms to the same schema — no fields are missing, only personalization is absent.

---

## 6. Security Considerations

- **No user-supplied text in flag names or IDs.** Feature flag metadata is sourced exclusively from `ALL_FEATURE_FLAGS` (a static constant). User input from conversation history never appears in the `generation_json` structural fields.
- **Company name sanitization.** The `company_name` field in `dummy_data_json` is extracted from conversation history via regex. Any HTML or script tags in user input should be stripped before inclusion (Phase 2 hardening).
- **Schema validation as a guard.** The `validate_schema` node prevents malformed output from reaching the frontend. If validation fails after retries, the pipeline emits best-effort output rather than an empty or structurally broken payload.
- **No secrets in output.** The preview JSON contains no API keys, tokens, or credentials. Session IDs are opaque UUIDs with no embedded user data.
- **Immutable source data.** `get_flag_snapshot()` returns a deep copy of `ALL_FEATURE_FLAGS`. The source constant is never mutated, preventing cross-session state leakage.
