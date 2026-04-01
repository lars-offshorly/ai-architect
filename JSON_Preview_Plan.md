# CLAUDE.md — JSON Preview Generator

## What this component does

The JSON Preview Generator is Component 2 of the Knit AI Onboarding System. It receives a classification payload from the AI Bundle Classifier (Component 1), and produces a complete Knit workspace JSON populated with personalized sample data. This JSON is rendered by the frontend as an interactive preview so the user can validate the AI's understanding before committing to workspace creation. Once approved, the JSON is handed off to the JSON App Generator (Component 3) for real provisioning.

The core job is: classification signals in → personalized Knit JSON out.

## System position

```
User → [AI Bundle Classifier] → ClassificationPayload → [JSON Preview Generator] → Knit JSON → [JSON App Generator] → Provisioned Workspace
                (Dev A)                                        (Dev B — you)                         (Dev C)
```

## Architecture

Built as a LangGraph StateGraph with 7 nodes in a linear pipeline. One conditional edge handles validation retry. The graph is stateless between invocations — all context comes from the input payload.

```
extract_user_context → resolve_bundles_to_flags → select_data_tier → generate_sample_data → build_kpi_metrics → validate_schema → emit_preview
                                                                                                                      ↓ (if invalid)
                                                                                                              retry → resolve_bundles_to_flags
```

---

## Input: ClassificationPayload

This is produced by Dev A's Bundle Classifier. Treat it as a read-only contract.

```python
class ClassificationPayload(BaseModel):
    session_id: str
    conversation_history: list[dict]     # [{role: "user"|"assistant", content: str}]
    industry: str                        # e.g. "Legal Services"
    domain: str                          # e.g. "legal_services"
    suggested_bundles: list[str]         # e.g. ["project_mgmt", "ticketing"]
    bundle_confidence: float             # 0.0 to 1.0
    entities: list[EntityType]           # PEOPLE, WORK, ASSET, FINANCE
    intents: list[IntentType]            # VIEW, MANAGE, OPTIMIZE, DELIVER, AUTOMATE
    inferred_metrics: list[str]          # e.g. ["capacity_utilization", "cycle_time"]
    terminology_map: dict[str, str]      # e.g. {"Project": "Matter", "Ticket": "Request"}
    needs_fallback: bool                 # True if classifier confidence is very low
    clarification_complete: bool         # True if all clarification rounds are done
```

### EntityType and IntentType

These are classification-level categories from the spec's "AI Categories" framework. They are NOT the same as permission intents (View, Add, Edit, Delete) in the Knit JSON.

- EntityType: PEOPLE, WORK, ASSET, FINANCE — what the user is talking about
- IntentType: VIEW, MANAGE, OPTIMIZE, DELIVER, AUTOMATE — what they want to accomplish

The preview generator primarily uses `intents` in `build_kpi_metrics` to weight which KPIs to prioritize. The `suggested_bundles` field is the main driver of the pipeline.

---

## Internal state: PreviewGeneratorState

This is the graph's working memory. Each node reads from it and returns a partial dict to update it.

```python
class PreviewGeneratorState(BaseModel):
    classification: ClassificationPayload          # Input (immutable)
    user_context: Optional[UserContext] = None      # Extracted business details
    resolved_bundle_ids: list[str] = []             # Which bundles were applied
    feature_flags: dict[str, bool] = {}             # All 69 flags with on/off state
    permission_services: list[str] = []             # Which perm services to include
    landing_pages: list[dict] = []                  # User landing page configs
    data_tier: Literal["tier_1","tier_2","tier_3"]  # Sample data strategy
    sample_employees: list[dict] = []               # Personalized employee records
    sample_projects: list[dict] = []                # Personalized project records
    sample_tickets: list[dict] = []                 # Personalized ticket records
    sample_weaves: list[dict] = []                  # Personalized weave records
    kpi_metrics: list[dict] = []                    # Resolved KPI widget configs
    schema_valid: bool = False                      # Validation result
    validation_errors: list[str] = []               # What failed validation
    retry_count: int = 0                            # Validation retry counter
    max_retries: int = 2                            # Max retries before best-effort emit
    output: Optional[dict] = None                   # The final Knit JSON
```

---

## Key data model: UserContext

Extracted from conversation_history by the first node. Captures everything we can learn about the user's business for personalization.

```python
class UserContext(BaseModel):
    company_name: Optional[str]
    company_size: Optional[str]              # "small", "mid-sized", "enterprise"
    industry_detail: Optional[str]           # More specific than classification.industry
    people: list[PersonDetail]               # Names, roles, departments mentioned
    teams: list[TeamDetail]                  # Team names, sizes, functions
    work_items: list[WorkItemDetail]         # Project types, methodologies, deadlines
    has_remote_teams: Optional[bool]
    has_clients: Optional[bool]              # External client work vs internal
    work_methodology: Optional[str]          # "agile", "waterfall", "hybrid"
    primary_concern: Optional[str]           # User's main pain point
    key_phrases: list[str]                   # Signal phrases for debugging/Tier 2
```

Supporting models:

```python
class PersonDetail(BaseModel):
    name: Optional[str]
    role: Optional[str]           # e.g. "Attorney", "Tech Lead"
    department: Optional[str]
    is_user: bool = False         # True if this is the person chatting

class TeamDetail(BaseModel):
    name: str                     # e.g. "Engineering", "Litigation"
    size: Optional[int]
    function: Optional[str]

class WorkItemDetail(BaseModel):
    name: Optional[str]
    work_type: str                # "sprint", "litigation", "support_request", "waterfall"
    has_deadlines: bool = False
    methodology: Optional[str]    # "agile", "waterfall", "kanban"
```

---

## Graph nodes (in execution order)

### 1. extract_user_context

- **Purpose:** Parse conversation history for business personalization signals
- **Input:** `state.classification.conversation_history`
- **Output:** `{user_context: UserContext}`
- **LLM call:** Yes (production). Currently keyword-based for testing.
- **What it extracts:** Company name/size, industry specifics, people/roles mentioned, team/department names, work types (sprints, litigation, support), methodology (agile/waterfall/hybrid), primary concern, key phrases
- **Fallback:** If nothing is extracted, all UserContext fields remain None and downstream nodes use generic defaults

**Production LLM prompt pattern:**
```
Extract business context from this conversation.
Return JSON matching the UserContext schema.
If something is not mentioned, leave it null.
Do not invent details that aren't in the conversation.
```

### 2. resolve_bundles_to_flags

- **Purpose:** Convert suggested_bundles into the complete feature flag map
- **Input:** `state.classification.suggested_bundles`
- **Output:** `{resolved_bundle_ids, feature_flags, permission_services, landing_pages}`
- **LLM call:** No — fully deterministic
- **Logic:** Starts from ALL_FEATURE_FLAGS (69 flags, all off). For each suggested bundle, enables its flags from the bundle registry. Recursively includes compatible addons (chat, video_call, smart_vault, announcements). Deduplicates everything.
- **Key data structure:** `ALL_FEATURE_FLAGS` dict (69 entries) + `BUNDLE_REGISTRY` dict (9 bundles)

### 3. select_data_tier

- **Purpose:** Decide sample data generation strategy
- **Input:** `state.classification.suggested_bundles`, `state.classification.needs_fallback`
- **Output:** `{data_tier: "tier_1"|"tier_2"|"tier_3"}`
- **LLM call:** No
- **Logic:**
  - Tier 1: All suggested bundles exist in registry → use static templates + personalization
  - Tier 2: Some bundles known, some not → LLM-generated data (future)
  - Tier 3: Unknown industry or fallback flag → generic placeholders
  - needs_fallback=True always forces Tier 3

### 4. generate_sample_data

- **Purpose:** Produce personalized employee, project, ticket, and weave records
- **Input:** `state.user_context`, `state.resolved_bundle_ids`, `state.classification.terminology_map`
- **Output:** `{sample_employees, sample_projects, sample_tickets, sample_weaves}`
- **LLM call:** Tier 2 only (not yet implemented). Tier 1 and 3 are deterministic.
- **Personalization logic:**
  - Selects role pool based on industry (LEGAL_ROLES, TECH_ROLES, CONSULTING_ROLES)
  - Uses extracted team names as department names
  - Names projects based on work_items from context (litigation matters get case names, sprints get sprint names)
  - Names tickets based on industry (legal gets "Court filing deadline extension", tech gets "Login page 500 error")
  - Applies terminology_map (Project→Matter, Ticket→Request)
- **Minimum records:** 8 employees, 5-7 projects (if project_mgmt bundle), 6 tickets (if ticketing bundle)

### 5. build_kpi_metrics

- **Purpose:** Assemble KPI widget configurations
- **Input:** `state.resolved_bundle_ids`, `state.classification.inferred_metrics`
- **Output:** `{kpi_metrics: list[dict]}`
- **LLM call:** No
- **Logic:** Merges default metrics from matched bundles with classifier-inferred metrics. Deduplicates by metric key. Each metric has: key, label, type (percentage/count/duration/status/ratio), source service.
- **Key data structure:** `METRICS_CATALOG` dict (17 metrics)

### 6. validate_schema

- **Purpose:** Business rule validation before emitting
- **Input:** Full state
- **Output:** `{schema_valid, validation_errors, retry_count}`
- **LLM call:** No
- **Rules checked:**
  - At least one feature flag must be enabled
  - If projects-module enabled, need >= 3 sample projects
  - If tickets-module enabled, need >= 3 sample tickets
  - Need >= 5 sample employees
- **Retry:** If validation fails and retry_count < max_retries (2), routes back to resolve_bundles_to_flags. After max retries, emits best-effort output.

### 7. emit_preview

- **Purpose:** Assemble the final Knit JSON structure
- **Input:** Full state
- **Output:** `{output: dict}` — the complete Knit workspace JSON
- **LLM call:** No

---

## Output: Knit JSON

The output matches the real Knit platform API response structure. Top-level keys:

```
{
  "chat":           { GET endpoints — user status, unread messages }
  "hrhub":          { GET /employees/me + sample_employees array }
  "notification":   { GET endpoints — announcements, unread count }
  "orchestration":  { GET /feature_flags (69 flags), GET /users/me }
  "tickets":        { sample_tickets array }
  "weaves":         { sample_weaves array }
  "projects":       { sample_projects array }
  "_preview_metadata": {
    session_id, industry, domain, bundles,
    kpi_metrics, user_context, terminology_map, approved
  }
}
```

The `_preview_metadata` key is preview-only — it carries context needed by the frontend for rendering and by the App Generator for provisioning. It gets stripped before final deployment.

### Feature flag output shape (inside orchestration.feature_flags)

```json
{
  "id": 1,
  "name": "projects-module",
  "description": "projects-module",
  "isEnabled": true,
  "module": "Global"
}
```

---

## Bundle registry

9 bundles defined. Each maps to feature flags, permission services, landing pages, and compatible addons.

| Bundle | Type | Flags | Perm services | Addons |
|--------|------|-------|---------------|--------|
| project_mgmt | Primary | 13 | projects, kpi, notifications | chat, video_call, smart_vault, announcements |
| ticketing | Primary | 13 | tickets, kpi, notifications | chat, announcements |
| hr_hub | Primary | 22 | hr_hub, kpi, notifications | chat, weaves, announcements |
| weaves | Primary | 3 | weaves | — |
| chat | Addon | 4 | — | — |
| video_call | Addon | 0 (gap) | — | — |
| smart_vault | Addon | 2 | ai_toolkit | — |
| announcements | Addon | 4 | notifications | — |
| calendar | Addon | 3 | calendar | — |

### Known gaps to confirm with team

1. video_call has no feature flag in the JSON — is it controlled elsewhere?
2. data_formulation and store permission services exist but no bundle maps to them
3. asset_mgmt mentioned in classifier scope but no bundle definition exists
4. chatbot-module vs chat-bot — same feature or different?
5. docbot-module — part of AI Toolkit or standalone?
6. Disabled flags (kanban, timeline, whiteboard, todos) — future modules?

---

## Metrics catalog

17 KPI metrics available across 4 categories:

**Delivery performance:** on_time_delivery_rate, project_health_status, avg_case_duration, upcoming_deadlines

**Operational efficiency:** avg_resolution_time, cycle_time, sla_compliance, billable_vs_nonbillable, workload_distribution

**Team productivity:** capacity_utilization, active_work_items, planned_vs_actual

**HR metrics:** active_headcount, attendance_rate, leave_balance_utilization, cases_per_attorney, case_load_distribution

---

## Sample data personalization

The extract_user_context node drives personalization across three dimensions:

**Role pools:** Legal → Senior Associate, Partner, Paralegal. Tech → Senior Developer, Tech Lead, QA Engineer. Consulting → Engagement Manager, Delivery Lead, Solutions Architect.

**Project naming:** Litigation work items → case names ("Martinez v. Apex Corp"). Sprint work items → sprint names ("Mobile App MVP — Sprint 12"). Waterfall → milestone names ("Enterprise Platform Migration").

**Ticket naming:** Legal industry → legal requests ("Court filing deadline extension"). Consulting → delivery requests ("Client UAT environment setup"). Tech with support → bug reports ("Login page 500 error").

Generic name pool: 10 culturally diverse first/last name pairs used for all sample employees and assignees.

---

## Data tier strategy

| Tier | Condition | Method | LLM? |
|------|-----------|--------|------|
| Tier 1 | All bundles in registry | Static templates + UserContext personalization | No |
| Tier 2 | Partial bundle match or recognized but niche industry | LLM generates domain-specific rows | Yes (future) |
| Tier 3 | Unknown industry or needs_fallback=True | Generic placeholder records | No |

Tier 2 rate limits: max 3 LLM calls per session, global RPM limit. Fallback chain: Tier 2 fail → Tier 1 → Tier 3. No code path should produce zero sample records.

---

## Edit sub-graph (separate from main pipeline)

Handles user modifications to the preview ("remove the chat module", "add a timeline widget").

```
parse_edit_instruction → apply_edit_to_preview → END
```

**EditAction vocabulary:** add_module, remove_module, add_kpi, remove_kpi, add_dashboard, remove_dashboard, unsupported

**State retention rule:** Only the targeted node in the JSON changes. Everything else is preserved. Cascading effects are handled (removing a module also removes its KPIs and sample data).

**parse_edit_instruction** is keyword-based for MVP, LLM-based for production. The prompt includes current module/KPI/dashboard IDs so the LLM maps fuzzy references to exact targets.

---

## API surface

```
POST /api/v1/preview/generate    — ClassificationPayload → Knit JSON
POST /api/v1/preview/edit        — {current_preview, edit_instruction} → updated Knit JSON
POST /api/v1/preview/approve     — {session_id} → {approved: true, preview_id}
GET  /api/v1/preview/health      — {status, bundle_registry_version}
```

---

## Phase timeline

| Phase | Weeks | Focus |
|-------|-------|-------|
| Phase 1 — Core pipeline | 3-5 | Deterministic graph, static data + personalization, validation |
| Phase 2 — LLM + Edit flow | 6-8 | Tier 2 generation, LLM edit parser, sanitization, edge cases |
| Phase 3 — API + Integration | 9-12 | FastAPI endpoints, upstream/downstream integration, load testing |

---

## File structure

```
knit_ai/
├── schemas/                    # Shared with all devs
│   ├── classification.py       # ClassificationPayload, EntityType, IntentType
│   ├── preview.py              # UserContext, PersonDetail, TeamDetail, WorkItemDetail
│   └── blueprint.py            # FinalBlueprint (Dev C's input)
├── bundles/
│   └── registry.py             # BUNDLE_REGISTRY, ALL_FEATURE_FLAGS, METRICS_CATALOG
├── llm/
│   └── client.py               # Shared LLM wrapper
├── preview_generator/
│   ├── state.py                # PreviewGeneratorState
│   ├── nodes/
│   │   ├── extract_context.py  # extract_user_context
│   │   ├── resolve_flags.py    # resolve_bundles_to_flags
│   │   ├── data_tier.py        # select_data_tier
│   │   ├── sample_data.py      # generate_sample_data
│   │   ├── kpi.py              # build_kpi_metrics
│   │   ├── validate.py         # validate_schema
│   │   └── emit.py             # emit_preview
│   ├── edit/
│   │   ├── parse.py            # parse_edit_instruction
│   │   └── apply.py            # apply_edit_to_preview
│   ├── graph.py                # build_preview_graph, compiled_graph
│   └── api.py                  # FastAPI endpoints
└── testing/
    ├── fixtures.py             # FIXTURE_SOFTWARE_CONSULTING, FIXTURE_LEGAL, FIXTURE_TECH
    └── contract_tests.py       # Schema validation tests
```

---

## Security

- Input sanitization: Strip HTML/script tags from user-provided text (terminology_map, edit instructions) before injecting into JSON
- Rate limiting: Per-session max 3 LLM calls for Tier 2. Global RPM limit on generator endpoint
- Session isolation: Preview JSON in session-scoped cache, destroyed on expiry or approval
- No persistent storage unless user provides email
- Prompt injection defense: User input wrapped in XML tags in LLM prompts
