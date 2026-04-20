# Bundle Alignment Plan

## Background

Three devs have been building in parallel and the bundle key definitions have drifted apart. The app generator introduced a new set of Pydantic schemas that conflict with what the preview generator actually produces and what the bundle catalog already defines. This needs to be reconciled before the pipeline can work end to end.

---

## Architecture Decision — Render Key (decided 2026-04-08)

The pipeline uses two distinct types of bundle keys that serve different purposes and must not be conflated:

**Catalog key** — the classifier's output. Identifies the customer's business domain (e.g. `hr_management`, `legal_services`, `education`). Defined in `src/templates/bundle_registry.yaml`. This key is internal to the AI pipeline and must never appear in the output payloads sent to the frontend.

**Render key** — the rendering backend profile (e.g. `hr_hub`, `project_mgmt`, `ticketing`). Defined in `src/agents/preview_generator/bundles/registry.py` (`BUNDLE_REGISTRY`). This is what the frontend uses to select which stores and components to render. It is what `bundle_key` in `generation_json` and `dummy_data_json` must contain.

**The single translation point** is a new `render_key` field added to each bundle entry in `bundle_registry.yaml`. `BundleCatalog` exposes a `catalog_to_render_key()` method. All pipeline code that needs this translation imports from the catalog — nothing else maintains its own mapping.

### Catalog key → Render key mapping

| Catalog key | Render key | Notes |
|---|---|---|
| `hr_management` | `hr_hub` | |
| `ticketing` | `ticketing` | |
| `project_mgmt` | `project_mgmt` | |
| `finance` | `project_mgmt` | Weaves-heavy but same store shape |
| `marketing` | `project_mgmt` | |
| `sales` | `project_mgmt` | |
| `healthcare` | `ticketing` | |
| `legal_services` | `ticketing` | |
| `construction_real_estate` | `project_mgmt` | ⚠ PM table splits this into Construction + Real Estate — confirm whether these become two catalog keys |
| `education` | `project_mgmt` | |
| `all_microservices` | `hr_hub` | Needs a composite registry entry; using `hr_hub` as richest single fallback for now |
| `generic` | `generic` | |

---

## The Problems

### Problem 1 — Bundle keys are inconsistent across all three systems

There are three places that define what bundles exist, and they don't agree with each other.

**File: `src/templates/bundle_registry.yaml` (canonical)**
Catalog keys: `hr_management`, `ticketing`, `project_mgmt`, `finance`, `marketing`, `sales`, `healthcare`, `legal_services`, `construction_real_estate`, `education`, `all_microservices`, `generic`

**File: `src/agents/preview_generator/bundles/registry.py`**
Render keys: `project_mgmt`, `ticketing`, `hr_hub`, `weaves`, `chat`, `video_call`, `smart_vault`, `announcements`, `calendar`

**File: `src/agents/app_generator/schemas.py`**
Keys used in `_BUNDLE_CONFIG_MODELS`: `hr_hub`, `project_ops`, `asset_mgmt`, `field_service`, `generic`

The app generator schemas use keys that match neither the catalog nor the preview registry. `project_ops` and `asset_mgmt` and `field_service` do not exist in either system. `ticketing` exists in the preview registry but not in schemas.py.

A translation map exists in `src/agents/preview_generator/nodes/resolve_flags.py` (`_CATALOG_TO_REGISTRY`) but only covers one case (`hr_management → hr_hub`) and is not visible to the rest of the pipeline. Once the `render_key` field is in the YAML, this dict must be replaced with a catalog import.

---

### Problem 2 — `kpi_definitions` type mismatch

**File: `src/agents/app_generator/schemas.py`**

All bundle config models define `kpi_definitions` as:
```python
kpi_definitions: list[KpiDefinitionItem] = Field(min_length=1)
```

Where `KpiDefinitionItem` is:
```python
class KpiDefinitionItem(BaseModel):
    key: str
    label: str
    unit: str
```

**File: `src/agents/preview_generator/nodes/emit.py`**

The `_build_config()` function puts this into the config dict:
```python
"kpi_definitions": kpi_keys,  # kpi_keys = [k.key for k in kpi_metrics]
```

That is a `list[str]`, not a `list[KpiDefinitionItem]`. When the app generator validates the output from the preview generator, this will fail schema validation every time.

---

### Problem 3 — Config field lists are duplicated and independently maintained

**File: `src/agents/preview_generator/nodes/emit.py`**

`_BUNDLE_CONFIG_FIELDS` defines which fields go into the config dict per bundle:
```python
_BUNDLE_CONFIG_FIELDS: dict[str, list[str]] = {
    "hr_hub": ["ticket_categories", "default_statuses", "default_priorities", "queue_names", "kpi_definitions"],
    "project_mgmt": ["task_statuses", "task_priorities", "milestone_statuses", "kpi_definitions"],
    "ticketing": ["work_order_statuses", "work_order_priorities", "service_types", "kpi_definitions"],
}
```

**File: `src/agents/app_generator/schemas.py`**

The same fields are encoded again as Pydantic model attributes on `HrHubConfig`, `ProjectOpsConfig`, etc.

These two lists will silently drift. There is no enforcement that they stay in sync.

---

### Problem 4 — `app_generator` does not use `BundleCatalog` at all

**File: `src/agents/app_generator/service.py`**

The app generator loads templates and assembles payloads with no reference to the bundle catalog. It has no way to know if the bundle key it receives is valid according to the catalog, and it re-defines bundle structure independently via `schemas.py`.

---

### Problem 5 — `schemas.py` bundle keys don't match the preview generator output

The preview generator produces `bundle_key: "project_mgmt"` in its output (the render key). The app generator's `_BUNDLE_CONFIG_MODELS` dispatch map has `project_ops`, not `project_mgmt`. When `validate_generation_json()` runs, it will look up `project_mgmt` in `_BUNDLE_CONFIG_MODELS`, find nothing, and raise `ValueError: Unknown bundle_key`.

Same applies to `ticketing` — it exists in the preview generator registry but has no entry in `schemas.py`.

`asset_mgmt` and `field_service` are in `schemas.py` but correspond to no catalog bundle and no registry render key. They are orphaned.

---

## Fixes

---

### Lars — Add `render_key` to YAML and expose it from `BundleCatalog`

**Files: `src/templates/bundle_registry.yaml`, `catalog/bundle_catalog.py`**

The bundle catalog YAML is the single source of truth for bundle identity. The `render_key` field is being added so that the catalog also owns the classification → rendering translation. Nothing else in the codebase should maintain a hardcoded mapping of catalog keys to render keys.

Tasks:
- Add `render_key: <value>` to every bundle entry in `bundle_registry.yaml` using the mapping table above.
- Add `render_key: str` to the `BundleDefinition` Pydantic model in `catalog/bundle_catalog.py`.
- Add a `catalog_to_render_key() -> dict[str, str]` method on `BundleCatalog` that returns the full mapping.
- Export `CANONICAL_BUNDLE_KEYS: frozenset[str]` (catalog keys) and `RENDER_KEYS: frozenset[str]` from `catalog/bundle_catalog.py` so CJ and JR can import them for validation rather than maintaining their own lists.
- Confirm whether `construction_real_estate` stays as one catalog key or splits into `construction` and `real_estate` based on the PM table. If it splits, add both entries with their own `render_key`.

---

### CJ — Replace translation shim with catalog import and fix `kpi_definitions` output

**Files: `src/agents/preview_generator/bundles/registry.py`, `src/agents/preview_generator/nodes/emit.py`, `src/agents/preview_generator/nodes/resolve_flags.py`**

Tasks:
- Replace the hardcoded `_CATALOG_TO_REGISTRY` dict in `resolve_flags.py` with a call to `BundleCatalog.catalog_to_render_key()`. The dict must go — it is a duplicate of what the YAML now owns.
- In `emit.py`, change both output JSONs to use the render key for `bundle_key`, not `state.bundle_key` (which is the catalog key). Specifically:
  - `generation_json`: change `bundle_key=state.bundle_key` → `bundle_key=registry_key`
  - `dummy_data_json`: same change
- Fix `_build_config()` in `emit.py`. The `kpi_definitions` value must emit full objects, not strings. `METRICS_CATALOG` already has `key`, `label`, and `type` — use all three:
  ```python
  # Current (wrong):
  "kpi_definitions": [k.key for k in kpi_metrics],

  # Should be:
  "kpi_definitions": [
      {"key": k.key, "label": k.label, "unit": k.type}
      for k in kpi_metrics
  ],
  ```
  Coordinate with JR to confirm the exact field names match `KpiDefinitionItem`.
- Rename `_BUNDLE_CONFIG_FIELDS` keys in `emit.py` from `"hr_hub"`, `"project_mgmt"`, `"ticketing"` — these are already render keys and should stay that way. No change needed here unless JR's config model field names differ.
- Confirm that `BUNDLE_REGISTRY` in `registry.py` has an entry for every render key in the mapping table above. Currently it has no entry for `generic`. Add one.

---

### JR — Fix `schemas.py` to use render keys and drop orphaned models

**Files: `src/agents/app_generator/schemas.py`, `src/agents/app_generator/validators.py`, `src/agents/app_generator/contract.py`**

Tasks:
- Update `_BUNDLE_CONFIG_MODELS` in `schemas.py` to use render keys only: `hr_hub`, `project_mgmt`, `ticketing`, `generic`. Remove `project_ops`, `asset_mgmt`, `field_service` — these have no corresponding catalog or registry entries and will never appear in a payload.
- Add a `TicketingConfig` Pydantic model for the `ticketing` render key. Its fields must match `_BUNDLE_CONFIG_FIELDS["ticketing"]` in CJ's `emit.py`: `work_order_statuses`, `work_order_priorities`, `service_types`, `kpi_definitions`.
- Rename `ProjectOpsConfig` → `ProjectMgmtConfig` and update its entry in `_BUNDLE_CONFIG_MODELS` from `"project_ops"` to `"project_mgmt"`.
- Remove `AssetMgmtConfig` and `FieldServiceConfig` entirely.
- Fix `KpiDefinitionItem`. The `unit` field is sourced from `KpiMetric.type` in the preview generator (e.g. `"percentage"`, `"count"`, `"duration"`). Confirm the exact string values with CJ and add a comment documenting the source.
- Import `RENDER_KEYS` from the catalog and assert at module load time that `_BUNDLE_CONFIG_MODELS.keys() == RENDER_KEYS` minus any render keys that are addons (chat, weaves, etc.) and don't produce config. This catches future drift at startup.
- The `_REQUIRED_GENERATION_KEYS` and `_REQUIRED_DUMMY_KEYS` frozensets were removed from `AppPayloadContract` in the cherry-pick conflict. Confirm whether `validate_contract()` still covers those structural checks via full schema validation. Do not leave the contract validation weaker than it was — make an explicit call either way and document it.

---

## Order of Work

1. **Lars** adds `render_key` to the YAML and exposes `catalog_to_render_key()` from `BundleCatalog`. Also confirms whether `construction_real_estate` stays one bundle or splits. **CJ and JR are blocked on this.**
2. **CJ** replaces `_CATALOG_TO_REGISTRY` with catalog import; updates `emit.py` to use render key in output payloads; fixes `kpi_definitions` shape.
3. **JR** rewrites `_BUNDLE_CONFIG_MODELS` to render keys; removes orphaned models; adds `TicketingConfig`; fixes `KpiDefinitionItem`.
4. **JR + CJ** do a joint field-by-field check that every field in `emit.py`'s `_BUNDLE_CONFIG_FIELDS` maps exactly to a field in the corresponding `schemas.py` config model.
5. Run `tests/integration/test_dev_a_to_preview_handoff.py` and `tests/integration/test_generator_validator.py` to confirm end-to-end validation passes.

---

## Files Involved

| File | Owner | Action |
|---|---|---|
| `src/templates/bundle_registry.yaml` | Lars | Add `render_key` field to every bundle entry |
| `catalog/bundle_catalog.py` | Lars | Parse `render_key` in `BundleDefinition`; add `catalog_to_render_key()` method; export `CANONICAL_BUNDLE_KEYS` and `RENDER_KEYS` |
| `src/agents/preview_generator/nodes/resolve_flags.py` | CJ | Replace `_CATALOG_TO_REGISTRY` dict with `BundleCatalog.catalog_to_render_key()` import |
| `src/agents/preview_generator/nodes/emit.py` | CJ | Use render key for `bundle_key` in both output JSONs; fix `kpi_definitions` to emit full objects |
| `src/agents/preview_generator/bundles/registry.py` | CJ | Add `generic` entry to `BUNDLE_REGISTRY` |
| `src/agents/app_generator/schemas.py` | JR | Rename keys to render keys; remove orphaned models; add `TicketingConfig`; import `RENDER_KEYS` for startup assertion |
| `src/agents/app_generator/validators.py` | JR | No changes needed once schemas are fixed |
| `src/agents/app_generator/contract.py` | JR | Resolve cherry-pick conflict; confirm contract validation coverage |

---

## Addendum — Real Sources of Truth

> Added after reviewing `docs/api-mocks.json` and `docs/sample_dummy_data.json`.

### Background

The `src/templates/bundles/*/app.json` files were created by Lars as placeholder scaffolding ("must be edited") and are not finalized specs. They should not be treated as authoritative definitions of bundle config field shapes.

The actual sources of truth for payload structure are:

- **`docs/api-mocks.json`** — Real production API response shapes from the Knit platform (feature flags, employees, tickets, KPIs, permissions, etc.). This is what the frontend already expects to receive from each service.
- **`docs/sample_dummy_data.json`** — Real shape of the `dummy_data_json.stores` payload consumed by the frontend to render preview data (tickets, projects, tasks, KPIs, weaves).

Everything in the pipeline that defines payload structure — `app.json` templates, `schemas.py` Pydantic models, and `emit.py` config field lists — should be derived from and validated against these two files.

---

### Problem 6 — `app.json` templates, `schemas.py`, and `emit.py` were written against placeholder data

The bundle config models in `schemas.py` (`HrHubConfig`, `ProjectOpsConfig`, etc.) and the field lists in `emit.py`'s `_BUNDLE_CONFIG_FIELDS` were shaped by the placeholder `app.json` files, not by the real API shapes in `api-mocks.json` and `sample_dummy_data.json`. This means the field contracts they enforce may not match what the frontend actually consumes.

---

### Updated Fix Order

The previously documented fix order assumed `app.json` templates were correct. It needs a prerequisite step:

1. **Lars** reviews `docs/api-mocks.json` and `docs/sample_dummy_data.json` and produces a confirmed field list for each bundle's `config` block and `stores` shape. This is a product decision, not a dev decision.
2. **Lars** updates the `app.json` template files to reflect the confirmed real field values sourced from `api-mocks.json` and `sample_dummy_data.json`. These files become the finalized per-bundle payload specs.
3. **CJ** updates `emit.py`'s `_BUNDLE_CONFIG_FIELDS` and `kpi_definitions` output to match the confirmed `app.json` specs.
4. **JR** rewrites the `schemas.py` Pydantic config models to match the confirmed `app.json` specs exactly. The models must mirror real API field shapes, not placeholder values.
5. **JR and CJ** do a joint field-by-field check that `emit.py` output matches `schemas.py` models.
6. Run integration tests to confirm the pipeline validates end to end.

### Updated Files Involved

| File | Owner | Action |
|---|---|---|
| `docs/api-mocks.json` | Lars | Reference only — source of truth for API field shapes |
| `docs/sample_dummy_data.json` | Lars | Reference only — source of truth for stores payload shapes |
| `src/templates/bundles/*/app.json` | Lars | Update from placeholder to real field values sourced from the above |
| `src/agents/preview_generator/nodes/emit.py` | CJ | Align `_BUNDLE_CONFIG_FIELDS` and `kpi_definitions` to confirmed `app.json` |
| `src/agents/app_generator/schemas.py` | JR | Rewrite config models to match real API shapes from confirmed `app.json` |
