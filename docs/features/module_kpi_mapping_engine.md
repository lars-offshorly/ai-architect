# Feature: Module and KPI Mapping Engine

## 1. Feature Overview

**Feature Name:** Module and KPI Mapping Engine

**Short Description:** A deterministic mapping system that translates a classified bundle key into the exact set of feature flags, permission services, landing pages, and KPI metrics the workspace preview should display.

**Business Purpose:** Ensure that when the AI classifier identifies a user's needs as (for example) "project management," the preview activates precisely the right modules (Projects, Dashboard, KPI, Chat) and surfaces the right performance metrics (on-time delivery, project health, cycle time) — not a generic or incorrect set.

**Problem It Solves:** The Knit platform has 69 feature flags, 9 bundle definitions, and 17 KPI metrics. Without a structured mapping engine, each bundle would require manual flag-by-flag configuration, leading to inconsistencies, missed addons, and KPI gaps. The mapping engine makes bundle-to-feature resolution automatic, consistent, and auditable.

---

## 2. Scope

### In Scope

- **Bundle Registry (`BUNDLE_REGISTRY`)** — 9 bundle definitions (4 primary, 5 addon), each specifying: `flags`, `permission_services`, `landing_pages`, `compatible_addons`, `default_metrics`.
- **Feature Flag Resolution (`resolve_bundles_to_flags`)** — translates catalog bundle keys to registry keys, resolves primary + addon flags, and produces a complete 69-flag array with correct `isEnabled` states.
- **Catalog-to-Registry Translation (`_CATALOG_TO_REGISTRY`)** — bridges the naming gap between Dev A's classifier output and the preview generator's internal registry.
- **Addon Recursion** — when a primary bundle includes compatible addons (e.g., `chat`, `smart_vault`), their flags and services are automatically merged.
- **KPI Metric Assembly (`build_kpi_metrics`)** — selects default metrics for the bundle, boosts with conversation-derived signals, deduplicates, and attaches sample display values.
- **Metrics Catalog (`METRICS_CATALOG`)** — 17 KPI definitions across 4 categories with type metadata.
- **Module Derivation** — `emit_preview` derives the active module list from enabled flags using `_FLAG_TO_MODULE`.

### Out of Scope

- Dynamic bundle creation or user-defined custom bundles.
- KPI metric value computation from real data sources — all values are static samples.
- Frontend rendering logic for KPI widgets or module navigation.
- Edit-time module addition/removal (Phase 2 edit sub-graph).
- Weighted KPI prioritization based on `IntentType` signals (documented in plan but not implemented in Phase 1).

### Limitations

- `video_call` addon has no corresponding feature flag in the registry — it is included as a bundle ID but enables zero flags.
- `data_formulation` and `store` permission services exist in the platform but no bundle maps to them.
- `asset_mgmt` is referenced in the classifier scope but has no bundle definition — it falls through to Tier 3.

---

## 3. Business Rules

1. **Every primary bundle must include its compatible addons.** When `project_mgmt` is resolved, `chat`, `video_call`, `smart_vault`, and `announcements` are automatically included. This is not optional — the addon list in `BUNDLE_REGISTRY` is authoritative.

2. **Flag resolution starts from all-disabled.** `get_flag_snapshot()` returns all 69 flags with `isEnabled: False`. Only flags explicitly listed in the resolved bundles are set to `True`. This prevents accidental flag leakage between sessions.

3. **Catalog key translation must happen before registry lookup.** The mapping:
   - `project_ops` → `project_mgmt`
   - `field_service` → `ticketing`
   - `hr_hub` → `hr_hub` (identity)
   - `asset_mgmt` → not in registry (Tier 3)
   - `generic` → not in registry (Tier 3)

4. **Unknown bundle keys do not cause errors.** If the bundle key is not in the registry (after translation), the flag resolution returns empty flags, and the pipeline falls through to Tier 3 generic data.

5. **KPI metrics are sourced from two places:**
   - **Bundle defaults** — the `default_metrics` list in the resolved bundle's registry entry.
   - **Conversation signals** — key phrases extracted by `extract_user_context` (e.g., "on time", "SLA", "utilization") are mapped to metric slugs via `_PHRASE_TO_METRIC`.
   - Deduplication preserves the first occurrence (bundle defaults take priority in ordering).

6. **Fallback KPIs must always exist.** If no metrics are resolved from either source, the pipeline falls back to `[capacity_utilization, active_work_items]`.

7. **Permission services and landing pages are deduplicated across all resolved bundles.** If both `project_mgmt` and `announcements` include `notifications`, it appears once in the output.

8. **Module names are derived, not configured.** The `modules` list in `generation_json` is computed from enabled flags using `_FLAG_TO_MODULE`, not stored in the bundle definition. This ensures the module list always reflects the actual flag state.

---

## 4. User Flow / Workflow

### Flag Resolution Flow

1. Pipeline receives `bundle_key` (e.g., `"project_ops"`) from the confirmed session.
2. `resolve_bundles_to_flags` translates `"project_ops"` → `"project_mgmt"` via `_CATALOG_TO_REGISTRY`.
3. Looks up `"project_mgmt"` in `BUNDLE_REGISTRY` → finds 13 flags, 3 permission services, 2 landing pages, 4 compatible addons.
4. Recursively resolves addons: `chat` (4 flags), `video_call` (0 flags), `smart_vault` (2 flags), `announcements` (4 flags).
5. Collects all resolved bundle IDs: `["project_mgmt", "chat", "video_call", "smart_vault", "announcements"]`.
6. Gets a fresh flag snapshot (69 flags, all `False`).
7. Enables the union of all flag names from resolved bundles.
8. Returns: `resolved_bundle_ids`, `feature_flags` (dict), `permission_services` (deduplicated list), `landing_pages` (deduplicated list).

### KPI Assembly Flow

1. `build_kpi_metrics` reads `resolved_bundle_ids[0]` (primary bundle) from state.
2. Retrieves `default_metrics` from `BUNDLE_REGISTRY["project_mgmt"]` → `["on_time_delivery_rate", "project_health_status", "cycle_time", "capacity_utilization"]`.
3. Reads `user_context.key_phrases` — e.g., `["on time", "deadline"]`.
4. Maps phrases to metric slugs via `_PHRASE_TO_METRIC` → `["on_time_delivery_rate", "upcoming_deadlines"]`.
5. Merges and deduplicates → `["on_time_delivery_rate", "project_health_status", "cycle_time", "capacity_utilization", "upcoming_deadlines"]`.
6. Looks up each slug in `METRICS_CATALOG` → full metric definition with type and source service.
7. Attaches deterministic sample values from type-indexed pools (e.g., percentage → `87.5`).
8. Returns `kpi_metrics` list of `KpiMetric` objects.

### Module Derivation Flow

1. `emit_preview` reads `feature_flags` dict from state.
2. For each enabled flag, checks `_FLAG_TO_MODULE` mapping (e.g., `"projects-module"` → `"Projects"`).
3. Collects and deduplicates module display names.
4. Writes to `generation_json.modules`.

---

## 5. Acceptance Criteria

- [ ] `project_mgmt` bundle enables exactly 13 primary flags plus addon flags for chat (4), smart_vault (2), and announcements (4).
- [ ] `ticketing` bundle enables its 13 flags plus addon flags for chat (4) and announcements (4).
- [ ] `hr_hub` bundle enables its 21 flags plus addon flags for chat (4), weaves (3), and announcements (4).
- [ ] Catalog key `project_ops` resolves identically to registry key `project_mgmt`.
- [ ] Catalog key `field_service` resolves identically to registry key `ticketing`.
- [ ] Unknown bundle key (e.g., `asset_mgmt`) produces empty flags and no errors.
- [ ] `resolved_bundle_ids` includes the primary bundle and all recursively resolved addons.
- [ ] Permission services are deduplicated — no duplicate entries in the output list.
- [ ] KPI metrics for `project_mgmt` include at minimum: `on_time_delivery_rate`, `project_health_status`, `cycle_time`, `capacity_utilization`.
- [ ] Conversation phrases like "SLA compliance" and "resolution time" cause the corresponding metrics to appear in the output.
- [ ] If no metrics are resolved, the fallback set `[capacity_utilization, active_work_items]` is used.
- [ ] Every `KpiMetric` has a `sample_value` that matches its declared type (float for percentage, int for count, etc.).
- [ ] `generation_json.modules` exactly reflects the set of enabled module flags — no more, no less.

---

## 6. Security Considerations

- **Static registry data only.** `BUNDLE_REGISTRY`, `ALL_FEATURE_FLAGS`, and `METRICS_CATALOG` are hardcoded constants defined at module load time. No user input can modify bundle definitions, flag lists, or metric catalogs.
- **Deep copy isolation.** `get_flag_snapshot()` returns a deep copy of the flag array. Mutations during pipeline execution do not affect the source data, preventing cross-request state contamination.
- **No privilege escalation via flag manipulation.** The preview JSON is rendered client-side for display purposes only. Enabled flags in the preview do not grant actual platform permissions — those are controlled by the provisioning step (Component 3).
- **Deterministic output.** Given the same `bundle_key` and `conversation_history`, the mapping engine always produces the same output. There are no random elements, timestamps used as seeds, or external data fetches that could introduce variability or be exploited.
- **Conversation-derived KPI signals are bounded.** The `_PHRASE_TO_METRIC` mapping is a closed set — only phrases that match known entries produce metric additions. Arbitrary user text cannot inject unknown metric slugs into the output.
