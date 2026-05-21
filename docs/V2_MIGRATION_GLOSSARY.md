# V2 Migration Glossary

**Draft author:** Laira  
**For finalization by:** CJ  
**Purpose:** Field-by-field terminology reference for the v1 → v2 tenant provisioning migration. Use this when reading code, writing tests, or reviewing PRs to quickly map old terms to new ones.

---

## 1. Schema Versions

| Version | String value | Where it appears |
|---|---|---|
| **v1** | `"1.0"` | `generation_json.schema_version` |
| **v2** | `"2.0"` | `TenantProvisioningManifest.schema_version` |

---

## 2. Top-Level Payload Changes

In v1 the pipeline produces **two separate payloads**. In v2 they collapse into **one manifest**.

| v1 payload | Purpose | v2 replacement |
|---|---|---|
| `generation_json` | Workspace configuration — feature flags, active modules, permission services, landing pages, bundle-specific config values | Eliminated — v2 derives all config from the manifest sections |
| `dummy_data_json` | Sample data stores — the actual records (tickets, tasks, employees, KPIs) seeded into the workspace | Becomes the **tenant provisioning manifest** — same data but expressed as catalog ID selections rather than full records |

During the migration both payloads coexist inside `AppPayload`:

```python
class AppPayload(BaseModel):
    generation_json: dict[str, object]    # v1 — kept for backward compat
    dummy_data_json: dict[str, object]    # v1 — kept for backward compat
    v2_manifest: dict[str, object] | None # v2 — optional until full cutover
```

After Phase 7 cutover, only `v2_manifest` is returned.

---

## 3. V1 → V2 Field Mapping

| v1 location | v1 field | v2 location | v2 field | What changed |
|---|---|---|---|---|
| `dummy_data_json` | `session_id` | top-level | `session_id` | Same value, promoted to top level |
| `dummy_data_json` | `company_name` | `tenant` | `company_name` | Nested inside `tenant` section |
| `dummy_data_json` | `bundle_key` | `tenant` | `industry` | Renamed — now an industry string (e.g. `"bpo_contact_center"`) not a bundle key (e.g. `"ticketing"`) |
| `generation_json` | `bundle_key` | `tenant` | `industry` | Same rename as above |
| `generation_json` | `schema_version` | top-level | `schema_version` | Value changes from `"1.0"` to `"2.0"` |
| `generation_json` | `feature_flags` | — | (removed) | v2 does not carry a flags list; the frontend infers features from selected resource IDs |
| `generation_json` | `modules` | — | (removed) | v2 has no explicit module list |
| `generation_json` | `config` | — | (removed) | Config values are split across manifest sections or owned by the catalog |
| `dummy_data_json.stores` | `tickets` / `queues` | `tickets` | `queues[]` | Full records replaced by `{id, name}` catalog refs |
| `dummy_data_json.stores` | `tasks` / `projects` / `milestones` | `projects` | `projects[]` | Full records replaced by `{id, name}` catalog refs |
| `dummy_data_json.stores` | `kpis` | `kpi` | `kpis[]` | Full KpiMetric objects replaced by `{id, name}` catalog refs |
| `dummy_data_json.stores` | `employees` | `hr_hub` | `employees[]` | Structure preserved but only mutable fields are set by the AI; id is a frozen catalog ref |
| — | (no v1 equivalent) | `dashboard` | `dashboards[]` | New section — dashboards were embedded in `config` / `stores` in v1 |
| — | (no v1 equivalent) | `hr_hub` | `request_types[]` | New section — HR request types are now explicit catalog selections |
| — | (no v1 equivalent) | top-level | `generated_at` | New — ISO 8601 UTC timestamp of when the manifest was produced |
| — | (no v1 equivalent) | `tenant` | `size_band` | New — e.g. `"200-500"`, `"enterprise"` |
| — | (no v1 equivalent) | `tenant` | `primary_region` | New — e.g. `"APAC"`, `"AMER"` |
| — | (no v1 equivalent) | `tenant` | `locale` | New — e.g. `"en-PH"`, `"en-US"` |
| — | (no v1 equivalent) | `tenant` | `timezone` | New — e.g. `"Asia/Manila"`, `"UTC"` |

---

## 4. V2 Manifest Sections

The v2 manifest always has exactly these top-level keys, regardless of bundle:

```
schema_version · session_id · generated_at · tenant · tickets · projects · dashboard · kpi · hr_hub
```

### `tenant`
Six fields the AI sets freely. All are mutable.

```json
{
  "company_name": "Nexora Connect",
  "industry": "bpo_contact_center",
  "size_band": "200-500",
  "primary_region": "APAC",
  "locale": "en-PH",
  "timezone": "Asia/Manila"
}
```

### `tickets`
The AI picks which queue IDs to include. Queue configuration (icon, email address, managers, allowed categories, member assignments) is **frozen in the catalog** and applied automatically by the provisioning service.

```json
{
  "queues": [
    { "id": 101, "name": "Customer Care" },
    { "id": 102, "name": "Billing Support" }
  ]
}
```

### `projects`
The AI picks which project IDs to include. Project leads, team assignments, start dates, and linked tasks are **frozen in the catalog**.

```json
{
  "projects": [
    { "id": 501, "name": "Client Onboarding 2026" }
  ]
}
```

### `dashboard`
The AI picks which dashboard IDs to include. Widget layout, KPI bindings, and the home-dashboard flag are **frozen in the catalog**.

```json
{
  "dashboards": [
    { "id": 701, "name": "Operations Overview" }
  ]
}
```

### `kpi`
The AI picks which KPI IDs to include. All KPI metadata (label, unit, source service) is **frozen in the catalog**.

```json
{
  "kpis": [
    { "id": 1, "name": "Average Handle Time" },
    { "id": 2, "name": "First Call Resolution" }
  ]
}
```

### `hr_hub`
Two sub-sections. `employees` is the only section where the AI sets per-row field values; `request_types` is ID-list only.

```json
{
  "employees": [
    {
      "id": 1,
      "position": "Team Lead",
      "team": "Customer Care",
      "department": "Operations",
      "job_title": "Senior Agent",
      "job_type": "Full-time",
      "job_level": "L3"
    }
  ],
  "request_types": [
    { "id": 801, "name": "Leave Request" },
    { "id": 802, "name": "Overtime Request" }
  ]
}
```

---

## 5. Frozen vs Mutable Fields

**Frozen** means the AI picks the catalog ID; everything else about that resource is owned by the catalog and applied by the provisioning service. The `name` field next to each ID is human-readable only — it is ignored at runtime.

**Mutable** means the AI sets the value directly.

| Section | Field | Frozen / Mutable |
|---|---|---|
| `tenant.company_name` | Full value | **Mutable** |
| `tenant.industry` | Full value | **Mutable** |
| `tenant.size_band` | Full value | **Mutable** |
| `tenant.primary_region` | Full value | **Mutable** |
| `tenant.locale` | Full value | **Mutable** |
| `tenant.timezone` | Full value | **Mutable** |
| `tickets.queues[].id` | ID only | **Frozen** (selects a catalog queue) |
| `tickets.queues[].name` | Display label | Frozen — for human readability only |
| `projects.projects[].id` | ID only | **Frozen** |
| `dashboard.dashboards[].id` | ID only | **Frozen** |
| `kpi.kpis[].id` | ID only | **Frozen** |
| `hr_hub.employees[].id` | ID only | **Frozen** (catalog employee ref) |
| `hr_hub.employees[].position` | Full value | **Mutable** |
| `hr_hub.employees[].team` | Full value | **Mutable** |
| `hr_hub.employees[].department` | Full value | **Mutable** |
| `hr_hub.employees[].job_title` | Full value | **Mutable** |
| `hr_hub.employees[].job_type` | Full value | **Mutable** |
| `hr_hub.employees[].job_level` | Full value | **Mutable** |
| `hr_hub.request_types[].id` | ID only | **Frozen** |

---

## 6. Key Concept Shifts

| v1 paradigm | v2 paradigm | Why it matters |
|---|---|---|
| **Two payloads** (`generation_json` + `dummy_data_json`) | **One manifest** (`TenantProvisioningManifest`) | Simpler API contract; BE consumes a single object |
| **Feature flags list** — explicitly enabled/disabled per bundle | **No flags list** — frontend infers active features from which resource IDs are present | Removes the need to maintain flag parity between registry and manifest |
| **Full records in stores** — tickets and employees carry all their fields | **Catalog refs + selective mutation** — only IDs are selected; employee role fields are the only mutable per-row data | The AI makes fewer decisions; the catalog owns the rest, reducing hallucination surface |
| **Untyped `stores` dict** — keys vary by bundle (`tasks`, `queues`, `projects`, etc.) | **Six typed sections** — same section names regardless of bundle | Type-safe schema; tests can assert against a fixed structure |
| **Bundle-specific config dict** — `task_statuses`, `ticket_categories`, etc. per bundle | **No config dict** — statuses, priorities, and enums come from the catalog at provisioning time | Catalog is single source of truth; no duplication to drift |
| **`bundle_key`** identifies the workspace template | **`tenant.industry`** identifies the industry (e.g. `bpo_contact_center`) | More precise routing; one industry → one canonical manifest |

---

## 7. Code Locations

| Item | File |
|---|---|
| v1 schema models (`GenerationJson`, `DummyDataJson`, `PreviewOutput`) | [src/agents/preview_generator/schemas.py](../src/agents/preview_generator/schemas.py) |
| v2 schema models (`TenantProvisioningManifest`, `TenantInfo`, section models) | [src/agents/preview_generator/schemas.py](../src/agents/preview_generator/schemas.py) |
| v1 emitter (`emit_preview`) | [src/agents/preview_generator/nodes/emit.py](../src/agents/preview_generator/nodes/emit.py) |
| v2 emitter (`emit_v2`) | [src/agents/preview_generator/nodes/emit.py](../src/agents/preview_generator/nodes/emit.py) |
| LLM structured-output contract (`SelectionResult`) | [src/agents/tenant_provisioning/schemas.py](../src/agents/tenant_provisioning/schemas.py) |
| `AppPayload` container (holds both v1 and v2 during migration) | [src/domain/models/app_payload.py](../src/domain/models/app_payload.py) |
| Canonical manifest files (v2 sample fixtures) | [new_json_samples/](../new_json_samples/) |
| Industry → bundle key mapping | [new_json_samples/industry_bundle_map.json](../new_json_samples/industry_bundle_map.json) |
