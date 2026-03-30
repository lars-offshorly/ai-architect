# Preview Generator — Implementation Plan

## Responsibility

Receives `(session_id, bundle_key, conversation_history, extracted_info)` and runs a
7-node LangGraph pipeline to produce a Knit workspace JSON populated with personalized
sample data. This JSON is the `generation_json` returned to the frontend as an interactive
preview before workspace provisioning.

---

## System Position

```
User
 └─ POST /sessions                     → ConversationFlow (Dev A)
 └─ POST /sessions/{id}/reply          → ConversationFlow (Dev A)
 └─ POST /sessions/{id}/confirm        → sets Session.confirmed + selected_bundle_key
 └─ POST /sessions/{id}/preview        → PreviewFlow → PreviewGeneratorService (Dev B)
```

---

## Dev A Integration Map

Before building anything, understand exactly what Dev A provides at preview time:

| What Dev A provides | Where it lives | How Dev B uses it |
|---|---|---|
| `Session.selected_bundle_key` | `SessionRepository` | Pipeline input |
| `Session.confirmed == True` | `SessionRepository` | Gate in preview router |
| `ConversationMessage(role, content, timestamp)` per turn | `ConversationRepository.get_messages(session_id)` | Passed as `conversation_history` |
| `ExtractedInfo` (LLM-populated per turn) | **Not persisted to session** — assembled in router | Seeded from messages; see note below |

**ExtractedInfo gap**: The preview router currently creates a bare `ExtractedInfo(session_id=session_id)`.
Dev A's `InterpreterService.Extractor` populates `ExtractedInfo` per turn (company_name,
industry_hint, employee_names, role_names, department_names, metrics) but never persists
it to the session. Fix for Phase 1: re-derive from conversation_history in the router using
Dev A's fields as documented. Fix for Phase 2: LLM re-extraction inside the pipeline.

**`AppGeneratorService` bypass**: `PreviewFlow` currently calls `AppGeneratorService.assemble()`
after `PreviewGeneratorService.generate()`. However, `AppGeneratorService` **ignores
`preview_data`** — it loads `generation_json` from a static disk template and only uses
the second `dummy_data` return value. Our Knit JSON must become `generation_json`. Phase 1
updates `PreviewFlow.run()` to build `AppPayload` directly from our output, bypassing
`AppGeneratorService` for this endpoint.

---

## Call Chain (After Phase 1)

```
POST /sessions/{id}/preview
  preview.py router
    └─ conv_repo.get_messages(session_id) → list[ConversationMessage]
    └─ PreviewFlow.run(session_id, bundle_key, history)
         └─ PreviewGeneratorService.generate(session_id, bundle_key, history)
              └─ compiled_graph.invoke(PreviewGeneratorState)
                   └─ [7 nodes] → output: {generation_json, dummy_data_json}
         └─ AppPayload(generation_json=knit_json, dummy_data_json=sample_stores)
    └─ AppPayloadResponseSchema(...)
```

---

## Pipeline

```
extract_user_context → resolve_bundles_to_flags → select_data_tier → generate_sample_data → build_kpi_metrics → validate_schema → emit_preview
                                                                                                                        ↓ (if invalid, retry_count < 2)
                                                                                                                retry → resolve_bundles_to_flags
```

---

## Phase 1 — Core Pipeline

**Goal**: `POST /sessions/{id}/preview` returns a real Knit JSON end-to-end.
No LLM calls. Deterministic. Tier 1 (known bundles) + Tier 3 (fallback) only.

### Files to create (inside `src/agents/preview_generator/`)

All existing files (`fetcher.py`, `modifier.py`, `dummy_data.py`, `validators.py`) are
**deleted**. `service.py` and `__init__.py` are **rewritten**.

---

#### Step 1 — `bundles/registry.py`

Three constants. No logic.

```python
ALL_FEATURE_FLAGS: dict[int, dict]
# 69 entries seeded from docs/api-mocks.json
# Shape: {id: int, name: str, description: str, isEnabled: False, module: str}
# All isEnabled set to False — resolve_flags enables them per bundle.

BUNDLE_REGISTRY: dict[str, BundleDefinition]
# 9 bundles: project_mgmt, ticketing, hr_hub, weaves,
#            chat, video_call, smart_vault, announcements, calendar
# Each BundleDefinition:
#   flags: list[str]          — feature flag names this bundle enables
#   permission_services: list[str]
#   landing_pages: list[dict] — {id, module, selectionAutoShow, default, showTutorial}
#   compatible_addons: list[str]
#   default_metrics: list[str]

METRICS_CATALOG: dict[str, MetricDefinition]
# 17 entries keyed by slug
# Each MetricDefinition: key, label, type, source_service
```

Source of truth for flag IDs and names: `docs/api-mocks.json`
(`orchestration.GET./feature_flags/all.response.results`).

---

#### Step 2 — `schemas.py`

Internal pipeline models only. Never serialized in API requests/responses.

```python
class PersonDetail(BaseModel):
    name: Optional[str]
    role: Optional[str]
    department: Optional[str]
    is_user: bool = False

class TeamDetail(BaseModel):
    name: str
    size: Optional[int]
    function: Optional[str]

class WorkItemDetail(BaseModel):
    name: Optional[str]
    work_type: str   # "sprint" | "litigation" | "waterfall" | "support_request"
    has_deadlines: bool = False
    methodology: Optional[str]

class UserContext(BaseModel):
    company_name: Optional[str]
    company_size: Optional[str]        # "small" | "mid-sized" | "enterprise"
    industry_detail: Optional[str]
    people: list[PersonDetail]
    teams: list[TeamDetail]
    work_items: list[WorkItemDetail]
    has_remote_teams: Optional[bool]
    has_clients: Optional[bool]
    work_methodology: Optional[str]
    primary_concern: Optional[str]
    key_phrases: list[str]
```

Why `UserContext` and not just `ExtractedInfo`: Dev A's `ExtractedInfo` has flat lists
(`role_names: list[str]`). `generate_sample_data` needs structured objects —
`work_items[].work_type` to pick project naming strategy, and role+department paired
per person for employee records. `ExtractedInfo` cannot carry this.

---

#### Step 3 — `state.py`

```python
class PreviewGeneratorState(BaseModel):
    # Inputs (set at graph entry)
    session_id: str
    bundle_key: str
    conversation_history: list[dict]   # [{role: str, content: str}]

    # Populated by nodes
    user_context: Optional[UserContext] = None
    resolved_bundle_ids: list[str] = []
    feature_flags: dict[str, bool] = {}
    permission_services: list[str] = []
    landing_pages: list[dict] = []
    data_tier: Optional[Literal["tier_1","tier_2","tier_3"]] = None
    sample_employees: list[dict] = []
    sample_projects: list[dict] = []
    sample_tickets: list[dict] = []
    sample_weaves: list[dict] = []
    kpi_metrics: list[dict] = []
    schema_valid: bool = False
    validation_errors: list[str] = []
    retry_count: int = 0
    max_retries: int = 2
    output: Optional[dict] = None
```

---

#### Step 4 — `nodes/extract_context.py`

**Phase 1**: Keyword-based only. No LLM.

Reads `state.conversation_history` (all turns, user+assistant) and produces `UserContext`.

Extraction logic:
- Company name: look for "at [Name]", "called [Name]", "our company [Name]"
- Industry/work type: match against keyword sets (litigation/matter/attorney → legal,
  sprint/standup/backlog → tech, engagement/consultant → consulting)
- Role names: extract capitalized role tokens adjacent to "as a", "our", "the team"
- Team names: extract tokens before "team", "department", "group"
- Work items: presence of "sprint" → work_type=sprint; "matter"/"case" → litigation;
  "milestone"/"phase" → waterfall

Fallback: all `UserContext` fields remain None if nothing is matched. Downstream nodes
use industry-generic defaults. This is acceptable for Phase 1 — Dev A's `Extractor`
already ran LLM extraction during conversation, so most signals are embedded in the
conversation text which we scan here.

---

#### Step 5 — `nodes/resolve_flags.py`

**Fully deterministic. No LLM.**

1. Start with `ALL_FEATURE_FLAGS` — all 69 entries, all `isEnabled: False`
2. Look up `state.bundle_key` in `BUNDLE_REGISTRY`
3. Enable flags listed under that bundle
4. Recursively include `compatible_addons` — look each up in `BUNDLE_REGISTRY`, enable their flags
5. Deduplicate flag list
6. Set `state.resolved_bundle_ids`, `state.feature_flags`, `state.permission_services`, `state.landing_pages`

If `bundle_key` not in `BUNDLE_REGISTRY`: set empty flags, log warning, continue (Tier 3 will handle it).

---

#### Step 6 — `nodes/data_tier.py`

**Fully deterministic. No LLM.**

```
bundle_key in BUNDLE_REGISTRY  → Tier 1
bundle_key not in BUNDLE_REGISTRY → Tier 3
```

Tier 2 is reserved for Phase 2 (partial match or niche industry). For Phase 1, only
Tier 1 and Tier 3 exist.

---

#### Step 7 — `nodes/sample_data.py`

**Phase 1: Tier 1 and Tier 3 only. Deterministic.**

Role pools (used for `sample_employees`):
- Legal: Senior Associate, Partner, Paralegal, Legal Counsel, Managing Partner
- Tech: Senior Developer, Tech Lead, QA Engineer, DevOps Engineer, Product Manager
- Consulting: Engagement Manager, Delivery Lead, Solutions Architect, Business Analyst
- Generic: Manager, Analyst, Coordinator, Specialist, Director

Generic name pool (10 culturally diverse first+last pairs) used for all records.

**Tier 1 personalization rules:**

- `industry_detail` from `user_context` selects role pool
- `user_context.teams[].name` → used as `department` on employees
- `user_context.people[].name` → substitute for first N generic names
- `user_context.work_items[].work_type`:
  - `"litigation"` → project names like "Martinez v. Apex Corp"
  - `"sprint"` → "Mobile App MVP — Sprint 12"
  - `"waterfall"` → "Enterprise Platform Migration"
  - default → "Project Alpha", "Project Beta", ...
- `user_context.company_name` → injected into `_preview_metadata`

Minimum record counts:
- employees: 8
- projects: 5 (if project_mgmt bundle resolved)
- tickets: 6 (if ticketing bundle resolved)
- weaves: 3 (if weaves bundle resolved)

**Tier 3**: generic placeholder records, no personalization.

Employee record shape: match `docs/api-mocks.json` `/employees/me` response shape.
Ticket record shape: match `docs/sample_dummy_data.json` ticket schema
(`id, ticketId, title, status, assignee, authorDetails, dueDate, priority`).

---

#### Step 8 — `nodes/kpi.py`

**Fully deterministic. No LLM.**

1. Get `default_metrics` from the resolved bundle in `BUNDLE_REGISTRY`
2. Append any metrics from `state.user_context.key_phrases` that match a slug in `METRICS_CATALOG`
3. Deduplicate by slug
4. Look up each slug in `METRICS_CATALOG` → full metric definition
5. Set `state.kpi_metrics`

---

#### Step 9 — `nodes/validate.py`

**Fully deterministic. No LLM.**

Rules:
1. At least one feature flag enabled
2. If `projects-module` flag enabled → `len(sample_projects) >= 3`
3. If `tickets-module` flag enabled → `len(sample_tickets) >= 3`
4. `len(sample_employees) >= 5`

On failure:
- `retry_count < max_retries (2)` → route back to `resolve_bundles_to_flags`
- `retry_count >= max_retries` → set `schema_valid = True` with best-effort emit (do not block)

---

#### Step 10 — `nodes/emit.py`

Assembles two outputs from full state:

**`generation_json`** (Knit API response format):
```json
{
  "chat":         { "GET./chat/user-status/me": {...}, "GET./chat/messages/unread": {...} },
  "hrhub":        { "GET./employees/me": { "response": {...employees...} } },
  "notification": { "GET./notifications/announcements": {...}, "GET./notifications/unread-count": {...} },
  "orchestration": {
    "GET./feature_flags/all": {
      "response": { "pages": {...}, "count": 69, "results": [...all 69 flags with isEnabled set...] }
    },
    "GET./users/me": {
      "response": { ...user fields..., "landingPages": [...] }
    }
  },
  "tickets":      { "GET./tickets": { "response": { "results": [...sample_tickets...] } } },
  "weaves":       { "GET./worksheets": { "response": { "results": [...sample_weaves...] } } },
  "_preview_metadata": {
    "session_id": "...", "bundle_key": "...",
    "kpi_metrics": [...], "user_context": {...},
    "sample_projects": [...], "approved": false
  }
}
```

Note: no top-level `"projects"` key — project records go only in `_preview_metadata`.
`landingPages` lives inside `orchestration.GET./users/me.response.landingPages`.
Feature flag envelope: `{pages: {...}, count: 69, results: [...]}`.

**`dummy_data_json`** (legacy format for `AppPayload` compat):
```json
{
  "schema_version": "1.0",
  "session_id": "...",
  "bundle_key": "...",
  "stores": {
    "employees": [...],
    "tickets":   [...],
    "weaves":    [...],
    "projects":  [...]
  }
}
```

Sets `state.output = {"generation_json": ..., "dummy_data_json": ...}`.

---

#### Step 11 — `pipeline.py`

```python
from langgraph.graph import StateGraph, END

def build_preview_graph() -> StateGraph:
    graph = StateGraph(PreviewGeneratorState)
    graph.add_node("extract_user_context", extract_user_context)
    graph.add_node("resolve_bundles_to_flags", resolve_bundles_to_flags)
    graph.add_node("select_data_tier", select_data_tier)
    graph.add_node("generate_sample_data", generate_sample_data)
    graph.add_node("build_kpi_metrics", build_kpi_metrics)
    graph.add_node("validate_schema", validate_schema)
    graph.add_node("emit_preview", emit_preview)

    graph.set_entry_point("extract_user_context")
    graph.add_edge("extract_user_context", "resolve_bundles_to_flags")
    graph.add_edge("resolve_bundles_to_flags", "select_data_tier")
    graph.add_edge("select_data_tier", "generate_sample_data")
    graph.add_edge("generate_sample_data", "build_kpi_metrics")
    graph.add_edge("build_kpi_metrics", "validate_schema")
    graph.add_conditional_edges(
        "validate_schema",
        _route_after_validation,   # returns "emit_preview" or "resolve_bundles_to_flags"
    )
    graph.add_edge("emit_preview", END)
    return graph

compiled_graph = build_preview_graph().compile()
```

---

#### Step 12 — `service.py` (rewrite)

```python
class PreviewGeneratorService:
    def generate(
        self,
        session_id: str,
        bundle_key: str,
        conversation_history: list[dict],   # [{role, content}]
    ) -> tuple[dict[str, object], dict[str, object]]:
        state = PreviewGeneratorState(
            session_id=session_id,
            bundle_key=bundle_key,
            conversation_history=conversation_history,
        )
        result = compiled_graph.invoke(state)
        output = result["output"]
        return output["generation_json"], output["dummy_data_json"]
```

No longer takes `TemplateRepository`. No longer synchronous-blocking on disk templates.

---

#### Step 13 — `__init__.py` (rewrite)

```python
from .service import PreviewGeneratorService
__all__ = ["PreviewGeneratorService"]
```

---

### Files to delete (content cleared)

| File | Replaced by |
|------|-------------|
| `fetcher.py` | `bundles/registry.py` + `nodes/resolve_flags.py` |
| `modifier.py` | `nodes/sample_data.py` |
| `dummy_data.py` | `nodes/sample_data.py` |
| `validators.py` | `nodes/validate.py` |

---

### Files outside `preview_generator/` touched in Phase 1

#### `src/api/deps.py`

Change `get_preview_generator_service()` — no longer depends on `TemplateRepository`:

```python
# Before
def get_preview_generator_service() -> PreviewGeneratorService:
    return PreviewGeneratorService(get_template_repository())

# After
def get_preview_generator_service() -> PreviewGeneratorService:
    return PreviewGeneratorService()
```

#### `src/orchestrators/preview_flow.py`

`AppGeneratorService.assemble()` ignores `preview_data` and loads `generation_json` from a
static disk template instead. Our Knit JSON must become `generation_json`. Phase 1 updates
`PreviewFlow.run()` to accept `conversation_history` and build `AppPayload` directly:

```python
def run(
    self,
    session_id: str,
    bundle_key: str,
    conversation_history: list[dict],
) -> AppPayload:
    generation_json, dummy_data_json = self._preview_gen.generate(
        session_id, bundle_key, conversation_history
    )
    display_name = self._display_names.get(bundle_key, bundle_key)
    return AppPayload(
        session_id=session_id,
        bundle_key=bundle_key,
        display_name=display_name,
        generation_json=generation_json,
        dummy_data_json=dummy_data_json,
    )
```

`AppGeneratorService` is not called from this path in Phase 1.

#### `src/api/routers/preview.py`

Assemble conversation history and pass to `PreviewFlow`. Remove unused `ExtractedInfo`
import (no longer needed here — extraction now happens inside the pipeline):

```python
@router.post("/{session_id}/preview", response_model=AppPayloadResponseSchema)
async def generate_preview(
    session_id: str,
    session_repo: SessionRepository = Depends(get_session_repository),
    conv_repo: ConversationRepository = Depends(get_conversation_repository),
    flow: PreviewFlow = Depends(get_preview_flow),
) -> AppPayloadResponseSchema:
    session = session_repo.get(session_id)  # raises SessionNotFoundError → 404
    if not session.confirmed or not session.selected_bundle_key:
        raise HTTPException(status_code=400, detail="Bundle must be confirmed first.")

    history = [
        {"role": m.role, "content": m.content}
        for m in conv_repo.get_messages(session_id)
    ]

    payload = flow.run(
        session_id=session_id,
        bundle_key=session.selected_bundle_key,
        conversation_history=history,
    )
    return AppPayloadResponseSchema(
        schema_version=payload.schema_version,
        session_id=payload.session_id,
        bundle_key=payload.bundle_key,
        display_name=payload.display_name,
        modules=payload.modules,
        generation_json=payload.generation_json,
        dummy_data_json=payload.dummy_data_json,
    )
```

---

### Phase 1 complete state check

After Phase 1, this call chain works end-to-end:
1. `POST /sessions` — Dev A classifies, returns `bundle_key`
2. `POST /sessions/{id}/confirm` — sets `session.confirmed = True`
3. `POST /sessions/{id}/preview` — returns Knit JSON with 69 real feature flags,
   enabled flags for the bundle, personalized employees/tickets/weaves, KPI metrics

No LLM calls in the preview pipeline. No disk templates. Fully deterministic.

---

## Phase 2 — LLM + Edit Flow

**Goal**: Higher-quality personalization, niche industry support, and user-driven edits.
Builds on Phase 1 without breaking any existing interfaces.

### Step 14 — Upgrade `nodes/extract_context.py` to LLM

Replace keyword scan with structured LLM call. Same input/output contract — only the
extraction mechanism changes. The node still produces `UserContext`.

```
Prompt pattern:
  Extract business context from this conversation.
  Return JSON matching UserContext schema.
  If not mentioned, leave null. Do not invent details.
  <conversation>{{history}}</conversation>
```

Fallback: if LLM call fails, run Phase 1 keyword logic. Never block the pipeline.

Rate limit: LLM calls in this node count toward the per-session limit (max 3).

---

### Step 15 — Add Tier 2 to `nodes/sample_data.py`

Trigger condition (from `select_data_tier`): bundle recognized but industry is niche or
`user_context` contains unusual terminology not in the standard role pools.

LLM generates domain-specific employee roles, project names, ticket titles using
`user_context` as the prompt context.

Fallback chain: Tier 2 LLM fail → Tier 1 static → Tier 3 generic.

Rate limit: Tier 2 LLM calls count toward per-session limit.

---

### Step 16 — `edit/parse.py`

Parses a plain-English edit instruction into a typed `EditAction`.

```python
class EditAction(BaseModel):
    action: Literal[
        "add_module", "remove_module",
        "add_kpi", "remove_kpi",
        "add_dashboard", "remove_dashboard",
        "unsupported"
    ]
    target_id: Optional[str]   # exact flag name, metric slug, or dashboard id
    reason: Optional[str]

# Phase 2a: keyword-based parser
# Phase 2b: LLM parser — prompt includes current module/KPI/dashboard IDs
#           so fuzzy references ("remove the chat thing") map to exact targets
```

Input sanitization: strip HTML/script tags from edit instruction before passing to LLM.

---

### Step 17 — `edit/apply.py`

Takes `(current_knit_json: dict, action: EditAction)` → `updated_knit_json: dict`.

State retention rule: only the targeted node changes. Everything else is preserved.
Cascading rules:
- `remove_module` also removes its KPIs from `_preview_metadata.kpi_metrics` and
  its sample data from `_preview_metadata.sample_*`
- `add_module` enables the flag and adds default metrics from `METRICS_CATALOG`

---

### Step 18 — New API endpoint in `src/api/routers/preview.py`

```
POST /sessions/{session_id}/preview/edit
Body: { "current_preview": {...}, "edit_instruction": "remove the chat module" }
Response: AppPayloadResponseSchema (updated Knit JSON)
```

No changes to `PreviewFlow` — the edit path calls `PreviewGeneratorService` methods
directly (or a thin `EditFlow` wrapper).

---

### Step 19 — Security hardening

- Input sanitization: strip HTML/`<script>` from `edit_instruction` and any
  user-provided text before injecting into LLM prompts or JSON output
- Prompt injection defense: wrap user content in XML tags in all LLM prompts
- Per-session LLM call counter (max 3 total across extract + sample + edit)
- Global RPM cap on `POST /preview` and `POST /preview/edit`

---

## File Structure (Final)

```
src/agents/preview_generator/
├── schemas.py                  # UserContext, PersonDetail, TeamDetail, WorkItemDetail
├── state.py                    # PreviewGeneratorState
├── pipeline.py                 # build_preview_graph(), compiled_graph
├── service.py                  # PreviewGeneratorService
├── __init__.py                 # exports PreviewGeneratorService
├── bundles/
│   └── registry.py             # ALL_FEATURE_FLAGS, BUNDLE_REGISTRY, METRICS_CATALOG
├── nodes/
│   ├── extract_context.py      # extract_user_context
│   ├── resolve_flags.py        # resolve_bundles_to_flags
│   ├── data_tier.py            # select_data_tier
│   ├── sample_data.py          # generate_sample_data (Tier 1+3 Phase 1, +Tier 2 Phase 2)
│   ├── kpi.py                  # build_kpi_metrics
│   ├── validate.py             # validate_schema
│   └── emit.py                 # emit_preview
└── edit/                       # Phase 2 only
    ├── parse.py                # parse_edit_instruction
    └── apply.py                # apply_edit_to_preview
```

Files removed:
- `fetcher.py`, `modifier.py`, `dummy_data.py`, `validators.py`

Files outside `preview_generator/` modified:
- `src/api/deps.py` (1 function)
- `src/orchestrators/preview_flow.py` (1 method)
- `src/api/routers/preview.py` (1 endpoint)
