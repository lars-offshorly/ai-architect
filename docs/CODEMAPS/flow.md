# System Flow

**Last Updated:** 2026-04-13

High-level input/output for every scenario. This is a connectivity check — not an implementation guide.

---

## Scenario 1 — Full Conversation Flow (Happy Path)

User chats, gets classified, confirms, then generates a preview.

```
POST /sessions
  IN:  { user_id, message, preselected_bundle_key?, preselected_intent? }
  OUT: { session_id, status, question?, bundle_key?, classification, recommendation }

         ↓ (user replies to clarification questions)

POST /sessions/{id}/reply
  IN:  { message, force_preview? }
  OUT: { status, question?, bundle_key?, classification, recommendation }

         ↓ (status reaches "ready_for_preview" or user explicitly confirms)

POST /sessions/{id}/confirm
  IN:  { confirmed: true, bundle_key? }
  OUT: { status: "ready_for_preview", bundle_key }

         ↓

POST /sessions/{id}/preview
  IN:  (no body — reads session state)
  OUT: AppPayload { generation_json, dummy_data_json, modules, bundle_key, display_name }
       └─ generation_json: feature flags, modules, config
       └─ dummy_data_json: employees, kpis, tasks/tickets, milestones/queues

         ↓ (Dev C consumes AppPayload)

POST /sessions/{id}/app
  IN:  { dummy_data_json }
  OUT: AppPayload (same shape, generated from static template + provided data)
```

---

## Scenario 2 — Early Preview (No Confirmation Required)

User says "show me a preview now" before or during conversation.

```
POST /sessions/{id}/preview/early
  IN:  (no body — reads session state)
  OUT: AppPayload + warning: "Preview generated with incomplete information"

Bundle key resolved in priority order:
  1. session.selected_bundle_key     ← confirmed
  2. session.preselected_bundle_key  ← user chose before chatting
  3. latest_recommendation.primary_bundle
  4. latest_classification.selected_bundle  (only if confidence >= 0.6)
  5. "all_microservices"             ← final fallback → rendered as "generic"
```

---

## Scenario 3 — Preselected Bundle (User Knows What They Want)

User skips classification — they already know the bundle.

```
POST /sessions
  IN:  { user_id, message, preselected_bundle_key: "project_mgmt" }
  OUT: { session_id, status, bundle_key: "project_mgmt" }
       Session.preselected_bundle_key is set immediately.

         ↓ (optional conversation still runs for context extraction)

POST /sessions/{id}/confirm
  IN:  { confirmed: true }

         ↓

POST /sessions/{id}/preview
  → pipeline runs with preselected bundle, no classification needed
```

---

## Scenario 4 — Edit Preview

User wants to tweak the generated preview without re-running the pipeline.

```
POST /sessions/{id}/preview/edit
  IN:  { instruction: "remove the chat module", current_preview: { ...AppPayload } }
  OUT: AppPayload (mutated) + warning?

Internal:
  instruction → parse_edit_instruction() → EditAction { action_type, target }
  EditAction + current_preview → apply_edit() → updated AppPayload
  No pipeline re-run. Pure JSON mutation with cascading effects.
  (removing a module also removes its KPIs and sample data)
```

---

## Preview Pipeline (Internal — runs inside Scenario 1, 2, 3)

```
Input: session_id, bundle_key, conversation_history, extraction_result?

extract_user_context
  → UserContext { company_name, industry, employee_count, teams, roles }
  (uses Dev A's ExtractionResult if present, else keyword scan, else empty)

resolve_bundles_to_flags
  → feature_flags[], permission_services[], landing_pages[]
  (known bundles: hr_management→hr_hub, project_mgmt, ticketing → Tier 1 flags)
  (everything else → Tier 3, generic flags)

select_data_tier
  → tier: 1 (known bundle) | 3 (fallback)

generate_sample_data
  → employees[], projects/tickets[], milestones/queues[], weaves[]
  (personalized with company name, industry if Tier 1)

build_kpi_metrics
  → kpis[] { key, label, type, sample_value }
  (bundle defaults + conversation signal boosting)

validate_schema
  → [valid] → emit_preview
  → [invalid, retries < 2] → back to resolve_bundles_to_flags
  → [retries exhausted] → emit_preview anyway

emit_preview
  → GenerationJson + DummyDataJson → PreviewOutput

Output: AppPayload { generation_json, dummy_data_json }
```

---

## What Each Endpoint Reads / Writes

| Endpoint | Reads | Writes |
|----------|-------|--------|
| `POST /sessions` | — | Session, ConversationMessage |
| `POST /sessions/{id}/reply` | Session, ConversationMessages | Session (classification, extraction) |
| `POST /sessions/{id}/confirm` | Session | Session.confirmed, selected_bundle_key |
| `POST /sessions/{id}/preview` | Session, ConversationMessages | — (stateless, returns payload) |
| `POST /sessions/{id}/preview/early` | Session, ConversationMessages | — |
| `POST /sessions/{id}/preview/edit` | Session (auth check only) | — (stateless, client sends full payload) |
| `POST /sessions/{id}/app` | Session | — |

---

## Connection Check

```
Dev A (Interpreter) → Session.accumulated_extraction, latest_classification
                    → ConversationMessages
                    ↓
Dev B (Preview Generator) reads both from session + conv repo
                    → AppPayload (generation_json + dummy_data_json)
                    ↓
Dev C (App Generator) receives dummy_data_json via POST /sessions/{id}/app
                    → Final provisioned workspace payload
```

Everything is connected through the `Session` object and in-memory repositories.
No direct agent-to-agent calls — all handoffs go through HTTP endpoints reading shared session state.
