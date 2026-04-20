# Preview Generator Pipeline — Codemap

**Last Updated:** 2026-04-13

## Overview

The preview generator is a 7-node LangGraph pipeline that transforms a bundle key and conversation history into a personalized workspace preview (Knit JSON config + sample data stores).

**Entry Point:** `src/agents/preview_generator/service.py::PreviewGeneratorService.generate()`

**Output:** `tuple[dict, dict]` → `(generation_json, dummy_data_json)`

---

## State Machine

**File:** `src/agents/preview_generator/state.py`

```python
class PreviewGeneratorState(BaseModel):
    # --- Inputs (set at entry, immutable) ---
    session_id: str
    bundle_key: str                                  # e.g. "hr_management", "project_mgmt"
    conversation_history: list[dict]                # [{role: "user"|"assistant", content: str}]
    extraction_result: ExtractionResult | None      # Dev A's accumulated context
    preselected_intent: str | None                  # User's chosen use-case
    catalog: BundleCatalog | None                   # Bundle registry + feature flags

    # --- Populated by nodes ---
    user_context: UserContext | None                # extract_user_context
    resolved_bundle_ids: list[str]                  # resolve_bundles_to_flags
    feature_flags: dict[str, bool]                  # flag_name → isEnabled
    permission_services: list[str]                  # resolve_bundles_to_flags
    landing_pages: list[dict]                       # resolve_bundles_to_flags
    data_tier: Literal["tier_1", "tier_2", "tier_3"] | None  # select_data_tier
    sample_employees: list[dict]                    # generate_sample_data
    sample_projects: list[dict]                     # generate_sample_data
    sample_tickets: list[dict]                      # generate_sample_data
    sample_weaves: list[dict]                       # generate_sample_data
    kpi_metrics: list[KpiMetric]                    # build_kpi_metrics
    schema_valid: bool                              # validate_schema
    validation_errors: list[str]                    # validate_schema
    retry_count: int                                # validate_schema
    max_retries: int                                # validate_schema (default: 2)
    output: PreviewOutput | None                    # emit_preview
```

---

## Pipeline DAG

```
extract_user_context
    ↓ (company, industry, people, teams, work_methodology, key_phrases)
resolve_bundles_to_flags
    ↓ (enabled_flags, permission_services, landing_pages, resolved_bundle_ids)
select_data_tier
    ↓ (Tier 1 | Tier 3)
generate_sample_data
    ↓ (sample_employees, sample_projects, sample_tickets, sample_weaves)
build_kpi_metrics
    ↓ (kpi_metrics list from bundle defaults + context signals)
validate_schema
    ├─ [valid or retries exhausted] → emit_preview → END
    └─ [invalid, retries remain] → resolve_bundles_to_flags (retry from this node)
```

**Retry Edge Logic:**
- Max retries: 2
- On validation failure: increment `retry_count`, jump back to `resolve_bundles_to_flags`
- On `retry_count >= max_retries`: continue to emit (best-effort output)

---

## Node: extract_user_context

**File:** `src/agents/preview_generator/nodes/extract_context.py`

### Purpose
Extract structured business context from conversation history and/or Dev A's extraction result.

### Input
- `state.conversation_history` — All user+assistant messages
- `state.extraction_result` — Dev A's accumulated `ExtractionResult` (optional)
- `state.preselected_intent` — User's chosen intent before chatting (optional)

### Output
- `state.user_context` → `UserContext` with:
  - `company_name` — e.g. "Acme Corp"
  - `company_size` — "small", "mid-sized", "enterprise"
  - `industry_detail` — e.g. "Legal Services", "Project Management"
  - `people` → list of `PersonDetail` (name, role, department, is_user)
  - `teams` → list of `TeamDetail` (name, size, function)
  - `work_items` → list of `WorkItemDetail` (type, methodology, has_deadlines)
  - `work_methodology` — "agile", "waterfall", "kanban", "hybrid"
  - `has_remote_teams` — boolean signal
  - `has_clients` — boolean signal
  - `primary_concern` — user's main pain point
  - `key_phrases` — ["on time", "deadline", "capacity", ...] for KPI matching

### Three-Tier Resolution

**Tier 1: Dev A extraction present**
- Map `extraction_result` fields → `UserContext`
- Keyword scan fills remaining None fields
- No redundant LLM call

**Tier 2: No extraction, but history present**
- Keyword scan on conversation text
- Future (Phase 2): LLM structured extraction

**Tier 3: No inputs**
- Return empty `UserContext()`

### Implementation
- Regex patterns for company name, people names, roles, teams, company size
- Keyword sets for industry detection, work types, methodologies
- Catalog-driven extraction (extraction_keywords per bundle)
- Case-insensitive matching with word boundary protection

---

## Node: resolve_bundles_to_flags

**File:** `src/agents/preview_generator/nodes/resolve_flags.py`

### Purpose
Translate bundle key → enabled feature flags, permission services, landing pages.

### Input
- `state.bundle_key` — e.g. "hr_management", "project_mgmt", "ticketing"
- `state.catalog` — BundleCatalog with all known bundles and flags

### Output
- `state.resolved_bundle_ids` — list of bundle keys (primary + addons)
- `state.feature_flags` — dict[flag_name → isEnabled]
- `state.permission_services` — list of service names (e.g. "hr_hub", "projects")
- `state.landing_pages` — list of landing page configs

### Tier 1 Canonical Keys
Only these bundles get full feature flag resolution:
- `hr_management` → hr_hub
- `project_mgmt` → project_mgmt
- `ticketing` → ticketing
- `generic` → generic
- `all_microservices` → all_microservices

Other keys (finance, sales, marketing, etc.) are treated as Tier 3 fallback (no flag resolution).

### Algorithm
1. Check if `bundle_key` is in Tier 1 canonical set
2. If yes: look up bundle definition in catalog
3. Collect primary bundle + all compatible_addons
4. For each bundle: enable its flags, union permission_services, union landing_pages
5. If bundle not found: return empty sets (will be handled by data_tier as fallback)

### Cascading Addons
Bundles can declare `compatible_addons` (e.g. "Projects" bundle can include "Chat" addon):
- Recursively resolve each addon
- Deduplicate flags by name

---

## Node: select_data_tier

**File:** `src/agents/preview_generator/nodes/data_tier.py`

### Purpose
Determine tier of sample data generation based on bundle recognition.

### Input
- `state.bundle_key` — Bundle to check
- `state.catalog` — For bundle lookup

### Output
- `state.data_tier` — "tier_1", "tier_2", or "tier_3"

### Logic
- **Tier 1:** Bundle is a canonical known bundle (hr_management, project_mgmt, ticketing) → full personalization
- **Tier 2:** (Phase 2) Known bundle + niche industry or missing context → LLM-enhanced data generation
- **Tier 3:** Unknown bundle or no context → generic placeholder records

**Current Implementation:** Only Tier 1 and Tier 3 active. Tier 2 deferred to Phase 2.

---

## Node: generate_sample_data

**File:** `src/agents/preview_generator/nodes/sample_data.py`

### Purpose
Create realistic sample employee, project, ticket, and weave records personalized to the context.

### Input
- `state.user_context` — Company, industry, people, teams, work methodology
- `state.data_tier` — Tier level (determines personalization depth)
- `state.bundle_key` — To know which store types to populate

### Output
- `state.sample_employees` — list[dict] with fields: id, name, email, role, department, ...
- `state.sample_projects` — list[dict] with fields: id, name, status, priority, assigned_to, ...
- `state.sample_tickets` — list[dict] with fields: id, title, status, priority, assignee, type, ...
- `state.sample_weaves` — list[dict] with fields: id, name, content, ...

### Tier 1 Personalization Rules

**Role Pools (by industry):**
- Legal: Senior Associate, Partner, Paralegal, Legal Counsel, Managing Partner
- Tech: Senior Developer, Tech Lead, QA Engineer, DevOps Engineer, Product Manager
- Consulting: Engagement Manager, Delivery Lead, Solutions Architect, Business Analyst
- Generic: Manager, Analyst, Coordinator, Specialist, Director

**Department Assignment:**
- Uses `user_context.teams[].name` as department names on employee records

**Person Names:**
- Substitutes `user_context.people[].name` for first N generic names

**Project Naming:**
- Work type "litigation" → "Martinez v. Apex Corp" style (legal case names)
- Work type "sprint" → "Mobile App MVP — Sprint 12"
- Work type "waterfall" → "Enterprise Platform Migration"
- Default → "Project Alpha", "Project Beta", ...

**Company Name:**
- Injected into internal metadata field `_preview_metadata.company_name`

**Minimum Record Counts:**
- Employees: 8
- Projects: 5 (if project_mgmt bundle)
- Tickets: 6 (if ticketing bundle)
- Weaves: 3 (if weaves bundle)

### Tier 3 Fallback
- Generic placeholder records, no personalization
- Always at least minimum counts

---

## Node: build_kpi_metrics

**File:** `src/agents/preview_generator/nodes/kpi.py`

### Purpose
Assemble a list of KPI metrics from bundle defaults and conversation signals.

### Input
- `state.user_context.key_phrases` — Extracted phrases like "on time", "capacity", "sla"
- `state.bundle_key` — To look up default metrics in catalog
- `state.catalog` — Metrics catalog (slug → KpiMetric definition)

### Output
- `state.kpi_metrics` — list[KpiMetric]:
  - `key` — slug (e.g. "on_time_delivery_rate")
  - `label` — display name (e.g. "On-Time Delivery Rate")
  - `type` — "percentage", "count", "duration", "status", "ratio"
  - `source_service` — owning service (e.g. "projects", "hr_hub")
  - `sample_value` — realistic value based on type

### Algorithm
1. Get default metrics for resolved bundle from catalog
2. Scan `user_context.key_phrases` for metric slugs
3. Deduplicate by slug
4. Look up each in metrics catalog → full KpiMetric definition
5. Set sample_value based on metric type:
   - percentage → 87.5
   - count → 42
   - duration → 3.2
   - status → "Healthy"
   - ratio → 0.72

### Bundled KPI Defaults
| Bundle | Default KPIs |
|--------|--------------|
| hr_management | active_headcount, attendance_rate, leave_balance_utilization, capacity_utilization |
| project_mgmt | on_time_delivery_rate, project_health_status, cycle_time, capacity_utilization |
| ticketing | avg_resolution_time, sla_compliance, active_work_items, cycle_time |
| Tier 3 (all others) | capacity_utilization, active_work_items |

---

## Node: validate_schema

**File:** `src/agents/preview_generator/nodes/validate.py`

### Purpose
Validate that generated state meets minimum data requirements. Determine retry routing.

### Input
- Full state with all previous node outputs

### Output
- `state.schema_valid` — boolean
- `state.validation_errors` — list of error messages
- `state.retry_count` — incremented if retrying
- Routing decision: "emit_preview" or "resolve_bundles_to_flags" (retry)

### Validation Rules
1. At least one feature flag enabled
2. If projects-module flag enabled → `len(sample_projects) >= 3`
3. If tickets-module flag enabled → `len(sample_tickets) >= 3`
4. If weaves-module flag enabled → `len(sample_weaves) >= 1`
5. `len(sample_employees) >= 5`

### Retry Logic
```
if all rules pass:
    → route to "emit_preview"
elif retry_count < max_retries (2):
    → increment retry_count
    → route to "resolve_bundles_to_flags" (re-sample data)
else:
    → route to "emit_preview" (best-effort, log warning)
```

---

## Node: emit_preview

**File:** `src/agents/preview_generator/nodes/emit.py`

### Purpose
Assemble the final two output dicts: `generation_json` (Knit config) and `dummy_data_json` (sample stores).

### Input
- Full resolved state with feature flags, sample data, KPIs, company name

### Output
- `state.output` → `PreviewOutput` with:
  - `generation_json` — Knit workspace configuration
  - `dummy_data_json` — Sample data stores

### generation_json Structure
```json
{
  "schema_version": "1.0",
  "bundle_key": "hr_management",
  "feature_flags": [
    {"id": 1, "name": "hrhub-module", "description": "...", "isEnabled": true, "module": "HRHub"},
    ...69 total flags...
  ],
  "modules": ["HRHub", "Dashboard", "KPI"],
  "config": {
    "permission_services": ["hr_hub", "kpi"],
    "landing_pages": [...],
    "ticket_categories": [...from sample_tickets types...],
    "default_statuses": [...from sample_tickets statuses...],
    "default_priorities": [...from sample_tickets priorities...],
    "queue_names": [...from sample_employees departments...],
    "kpi_definitions": [
      {"key": "active_headcount", "label": "Active Headcount", "unit": "count"},
      ...
    ]
  }
}
```

### dummy_data_json Structure
```json
{
  "bundle_key": "hr_management",
  "session_id": "uuid",
  "company_name": "Acme Corp" (or null),
  "stores": {
    "kpis": [
      {
        "id": 1,
        "key": "active_headcount",
        "label": "Active Headcount",
        "type": "count",
        "source_service": "hr_hub",
        "sample_value": 42
      },
      ...
    ],
    "tickets": [...sample_tickets...],
    "queues": [...sample_projects...],
    "employees": [...sample_employees...],
    "dashboard_widgets": []
  }
}
```

### Store Key Mapping
| Bundle | Primary Store | Secondary Store | Weaves Store |
|--------|--------------|-----------------|--------------|
| hr_management | tickets | queues | — |
| project_mgmt | tasks | milestones | — |
| ticketing | tickets | queues | — |
| weaves | — | — | weaves |
| Tier 3 (fallback) | items | projects | — |

### Config Field Derivation
- `ticket_categories` ← unique types from sample_tickets
- `default_statuses` ← unique statuses from sample_tickets
- `default_priorities` ← unique priorities from sample_tickets
- `queue_names` ← unique departments from sample_employees
- `kpi_definitions` ← derived from state.kpi_metrics

---

## Edit Sub-graph (Phase 2)

### Overview
Enables users to modify a preview via natural language instructions without re-running the full pipeline.

### Node: parse_edit_instruction

**File:** `src/agents/preview_generator/edit/parse.py`

Converts user instruction → `EditAction` schema.

```python
class EditActionType(str, Enum):
    ADD_MODULE = "add_module"
    REMOVE_MODULE = "remove_module"
    ADD_KPI = "add_kpi"
    REMOVE_KPI = "remove_kpi"
    ADD_DASHBOARD = "add_dashboard"
    REMOVE_DASHBOARD = "remove_dashboard"
    UNSUPPORTED = "unsupported"

class EditAction(BaseModel):
    action_type: EditActionType
    target: str | None = None  # flag name, KPI slug, or dashboard ID
    raw_instruction: str
```

**Parsing Strategy:**
1. Lowercase instruction
2. Check for dashboard action (if "dashboard" + add/remove verb)
3. Check for KPI action (lookup by slug or label in metrics_catalog)
4. Check for module action (lookup in _MODULE_MAP with flag names)
5. Regex fallback for "add kpi XYZ" or "remove kpi XYZ"
6. If nothing matches → `EditActionType.UNSUPPORTED`

**Module Label → Flag Map:**
```
"hr" → "hrhub-module"
"hr hub" → "hrhub-module"
"projects" → "projects-module"
"tickets" → "tickets-module"
"dashboard" → "dashboard-module"
"kpi" → "kpi-module"
"chat" → "chat-module"
... (see _MODULE_MAP in parse.py)
```

### Node: apply_edit

**File:** `src/agents/preview_generator/edit/apply.py`

Applies an `EditAction` to a preview payload.

```python
def apply_edit(
    payload: dict,  # Original preview payload (not mutated)
    action: EditAction,
    catalog: BundleCatalog,
) -> tuple[dict, str | None]:
    # Deep copy payload to avoid mutation
    # Apply action
    # Return (updated_payload, warning_or_None)
```

**Actions:**

#### ADD_MODULE (flag_name)
- Enable the flag in feature_flags
- Add display module name to modules[] (if not present)

#### REMOVE_MODULE (flag_name)
- Disable the flag
- Remove display module name from modules[]
- **Cascade:** Remove related KPIs from config.kpi_definitions and stores.kpis
- **Cascade:** Remove related store keys (e.g., removing "tickets-module" removes stores.tickets)

#### ADD_KPI (kpi_slug)
- Look up slug in metrics_catalog
- Add to stores.kpis (skip if already present)
- Add to config.kpi_definitions
- Return warning if KPI not found

#### REMOVE_KPI (kpi_slug)
- Remove from stores.kpis
- Remove from config.kpi_definitions

#### ADD_DASHBOARD
- Enable "dashboard-module" flag
- Add "Dashboard" to modules[]

#### REMOVE_DASHBOARD
- Disable "dashboard-module" flag
- Remove "Dashboard" from modules[]
- Remove stores.dashboard_widgets

#### UNSUPPORTED
- Return original payload with warning message

**State Retention Rule:**
- Only the targeted part changes
- Everything else is preserved
- No re-sampling or re-validation

---

## Service Wrapper

**File:** `src/agents/preview_generator/service.py`

```python
class PreviewGeneratorService:
    def __init__(self, catalog: BundleCatalog):
        self._catalog = catalog

    def generate(
        self,
        session_id: str,
        bundle_key: str,
        conversation_history: list[dict],
        extraction_result: ExtractionResult | None = None,
        preselected_intent: str | None = None,
    ) -> tuple[dict, dict]:
        # Create PreviewGeneratorState
        # Invoke compiled_graph.invoke(state)
        # Extract output.generation_json and output.dummy_data_json
        # Return tuple
```

**No TemplateRepository dependency.** All data is generated programmatically.

---

## Graph Compilation

**File:** `src/agents/preview_generator/pipeline.py`

```python
from langgraph.graph import StateGraph, END

_workflow = StateGraph(PreviewGeneratorState)

# Add nodes
_workflow.add_node("extract_user_context", extract_user_context)
_workflow.add_node("resolve_bundles_to_flags", resolve_bundles_to_flags)
_workflow.add_node("select_data_tier", select_data_tier)
_workflow.add_node("generate_sample_data", generate_sample_data)
_workflow.add_node("build_kpi_metrics", build_kpi_metrics)
_workflow.add_node("validate_schema", validate_schema)
_workflow.add_node("emit_preview", emit_preview)

# Linear edges
_workflow.set_entry_point("extract_user_context")
_workflow.add_edge("extract_user_context", "resolve_bundles_to_flags")
_workflow.add_edge("resolve_bundles_to_flags", "select_data_tier")
_workflow.add_edge("select_data_tier", "generate_sample_data")
_workflow.add_edge("generate_sample_data", "build_kpi_metrics")
_workflow.add_edge("build_kpi_metrics", "validate_schema")

# Conditional edge from validate_schema
_workflow.add_conditional_edges(
    "validate_schema",
    route_after_validation,  # Returns ROUTE_EMIT or ROUTE_RETRY
    {
        ROUTE_EMIT: "emit_preview",
        ROUTE_RETRY: "resolve_bundles_to_flags",
    },
)

_workflow.add_edge("emit_preview", END)

compiled_graph = _workflow.compile()
```

---

## Testing

**Key Test Files:**
- `tests/integration/test_preview_generator_flow.py` — 45+ tests covering all bundles, tiers, scenarios
- `tests/integration/test_dev_a_to_preview_handoff.py` — HTTP integration with session flow
- `tests/unit/preview_generator/test_extract_context.py` — Context extraction logic
- `tests/unit/preview_generator/test_sample_data_population.py` — Sample data generation
- `tests/unit/preview_generator/test_kpi.py` — KPI metric resolution
- `tests/unit/preview_generator/test_edit_parse.py` — Edit instruction parsing
- `tests/unit/preview_generator/test_edit_apply.py` — Edit application

**Execution Time:** ~500ms-2s for full pipeline (depending on LLM calls if enabled)

---

## Performance Characteristics

| Operation | Time | Notes |
|-----------|------|-------|
| extract_user_context | ~10-50ms | Regex-based (Phase 1); LLM optional Phase 2 |
| resolve_bundles_to_flags | ~5ms | Catalog lookup |
| select_data_tier | <1ms | Simple logic |
| generate_sample_data | ~50-100ms | Deterministic sampling |
| build_kpi_metrics | ~10ms | Catalog lookup + merge |
| validate_schema | <1ms | Rule checking |
| emit_preview | ~10-20ms | JSON assembly |
| **Total** | ~100-300ms | Without LLM calls |

With LLM calls (Phase 2): add ~500ms per LLM invocation.

---

## Future Enhancements (Phase 2)

- [ ] LLM-based extraction in `extract_user_context` (with keyword fallback)
- [ ] Tier 2 data generation for niche industries (LLM-enhanced naming/roles)
- [ ] LLM-based edit instruction parsing (for fuzzy references)
- [ ] Per-session LLM call counter (max 3 total)
- [ ] Global RPM limiting on preview endpoints
- [ ] Schema version migration path
