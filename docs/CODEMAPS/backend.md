# Backend Architecture — Codemap

**Last Updated:** 2026-04-13

## Overview

The FastAPI backend implements a three-agent onboarding pipeline:
1. **Interpreter Agent** (Dev A) — Conversation + bundle classification
2. **Preview Generator Agent** (Dev B) — Personalized workspace preview
3. **App Generator Agent** (Dev C) — Workspace provisioning

This map covers the API layer, routers, dependency injection, and orchestrators.

---

## API Entry Point

**File:** `src/api/app.py`

```python
def create_app() -> FastAPI:
    # Creates FastAPI instance with:
    # - CORS middleware (debug mode: allow all; prod: none)
    # - AuthMiddleware (validates tokens)
    # - RateLimitMiddleware (per-endpoint quotas)
    # - Routers: session, preview, bundles, app, health, (mock)
    # - Static files: frontend served from src/frontend/
```

### Lifespan Events
- **Startup:** Initialize Database, Pinecone
- **Shutdown:** Close Database, Pinecone

---

## API Routes

### Sessions Router
**File:** `src/api/routers/session.py`

| Endpoint | Method | Purpose | Response |
|----------|--------|---------|----------|
| `/sessions` | POST | Create new session | `SessionResponse` (session_id, created_at) |
| `/sessions/{id}/reply` | POST | Send message turn | `ConversationResponse` (latest turn, classification) |
| `/sessions/{id}/confirm` | POST | Confirm bundle selection | `SessionResponse` (confirmed=true, selected_bundle_key) |

**Key Logic:**
- `POST /reply` calls `ConversationFlow.run()` which invokes Interpreter + Replier services
- `POST /confirm` sets `session.confirmed = True` and persists `selected_bundle_key`
- All endpoints validate session exists before processing

---

### Preview Router
**File:** `src/api/routers/preview.py`

| Endpoint | Method | Purpose | Response |
|----------|--------|---------|----------|
| `/sessions/{id}/preview` | POST | Generate confirmed preview | `AppPayloadResponseSchema` |
| `/sessions/{id}/preview/early` | POST | Generate unconfirmed preview | `AppPayloadResponseSchema` + warning |
| `/sessions/{id}/preview/edit` | POST | Apply edit to preview | `AppPayloadResponseSchema` |

**Detailed Behavior:**

#### `POST /sessions/{id}/preview` (Confirmed)
- **Gate:** Requires `session.confirmed == True` and `session.selected_bundle_key` set
- **Calls:** `PreviewFlow.run()` with `conversation_history` from `ConversationRepository`
- **Returns:** Full `AppPayload` with `generation_json` (Knit config) + `dummy_data_json` (sample data)

#### `POST /sessions/{id}/preview/early` (Unconfirmed)
- **Gate:** No confirmation required
- **Bundle Resolution (priority order):**
  1. `session.selected_bundle_key` (if confirmed)
  2. `session.preselected_bundle_key` (if user chose before chatting)
  3. `session.latest_recommendation.primary_bundle` (best recommendation)
  4. `session.latest_classification.selected_bundle` (if confidence >= 0.6)
  5. Fallback: `"all_microservices"` → rendered as `"generic"`
- **Returns:** `AppPayloadResponseSchema` with warning: "Preview generated with incomplete information."

#### `POST /sessions/{id}/preview/edit` (Edit)
- **Input:** `EditPreviewRequestSchema` with `current_preview` (full payload) + `instruction` (natural language)
- **Process:**
  1. `parse_edit_instruction()` converts instruction → `EditAction` (add/remove module/KPI/dashboard)
  2. `apply_edit()` performs JSON mutation (no pipeline re-run)
- **Returns:** Updated `AppPayloadResponseSchema`

---

### Bundles Router
**File:** `src/api/routers/bundles.py`

| Endpoint | Method | Purpose | Response |
|----------|--------|---------|----------|
| `/bundles` | GET | List all bundles | `list[BundleMetadata]` |
| `/bundles/{key}` | GET | Get bundle details | `BundleMetadata` |
| `/bundles/{key}/kpis` | GET | Get bundle's default KPIs | `list[KpiMetric]` |

---

### App Router
**File:** `src/api/routers/app.py`

| Endpoint | Method | Purpose | Response |
|----------|--------|---------|----------|
| `/sessions/{id}/app` | POST | Provision workspace | `ProvisioningResponse` (workspace_id, status) |

**Process:**
1. Validates session + preview state
2. Calls `AppGeneratorService.generate()` to provision Knit workspace
3. Returns provisioning status

---

### Health Router
**File:** `src/api/routes/health.py`

| Endpoint | Method | Purpose | Response |
|----------|--------|---------|----------|
| `/health` | GET | Health check | `{"status": "ok"}` |

---

## Request/Response Schemas

**File:** `src/api/schemas/`

### Session Creation
```
POST /sessions
Body: {} (empty)
Response:
{
  "session_id": "uuid",
  "created_at": "2026-04-13T12:34:56Z"
}
```

### Conversation Reply
```
POST /sessions/{id}/reply
Body: {
  "message": "We're a legal firm with 5 attorneys"
}
Response:
{
  "session_id": "uuid",
  "turn_count": 2,
  "latest_message": {
    "role": "user" | "assistant",
    "content": "..."
  },
  "classification": {
    "selected_bundle": { "bundle_key": "...", "confidence": 0.95, ... },
    "ranked_candidates": [...],
    "missing_context": [...]
  }
}
```

### Confirm Bundle
```
POST /sessions/{id}/confirm
Body: {
  "bundle_key": "hr_management"  # Must match classification.selected_bundle
}
Response:
{
  "session_id": "uuid",
  "confirmed": true,
  "selected_bundle_key": "hr_management"
}
```

### Generate Preview
```
POST /sessions/{id}/preview
Body: {} (empty)
Response:
{
  "schema_version": "1.0",
  "session_id": "uuid",
  "bundle_key": "hr_management",
  "display_name": "Human Resources",
  "modules": ["HRHub", "Dashboard", "KPI"],
  "generation_json": { ... 69 feature flags, config ... },
  "dummy_data_json": { "stores": { "employees": [...], ... } },
  "warning": null
}
```

### Edit Preview
```
POST /sessions/{id}/preview/edit
Body: {
  "current_preview": { ... full preview payload ... },
  "instruction": "remove the chat module and add projects"
}
Response:
{
  "schema_version": "1.0",
  "session_id": "uuid",
  ... (updated preview)
}
```

---

## Dependency Injection

**File:** `src/api/deps.py`

All services and repositories are created via cached dependency providers (LRU cache, process-scoped):

```python
@lru_cache(maxsize=1)
def get_bundle_catalog() -> BundleCatalog:
    # Loaded from BUNDLE_REGISTRY_PATH (default: catalog/bundle_registry.yaml)
    # Validated against TEMPLATES_DIR for consistency

@lru_cache(maxsize=1)
def get_session_repository() -> SessionRepository:
    # In-memory store of Session objects

@lru_cache(maxsize=1)
def get_conversation_repository() -> ConversationRepository:
    # In-memory store of ConversationMessage objects

@lru_cache(maxsize=1)
def get_preview_generator_service() -> PreviewGeneratorService:
    # Thin wrapper around compiled LangGraph pipeline

@lru_cache(maxsize=1)
def get_preview_flow() -> PreviewFlow:
    # Orchestrator that composes preview generator + app payload assembly

@lru_cache(maxsize=1)
def get_interpreter_service() -> InterpreterService:
    # Dev A's bundle classifier

@lru_cache(maxsize=1)
def get_conversation_flow() -> ConversationFlow:
    # Orchestrator for conversation turns
```

---

## Orchestrators

### ConversationFlow
**File:** `src/orchestrators/conversation_flow.py`

Handles a single conversation turn:

```python
def process_turn(
    session_id: str,
    user_message: str,
    previous_extracted_info: ExtractionResult | None = None,
) -> tuple[ConversationMessage, ClassificationResult, str]:
    # 1. Store user message in ConversationRepository
    # 2. Call InterpreterService.classify()
    #    → updates session.latest_classification
    # 3. Call ReplierService.generate_reply()
    #    → generates assistant message based on classification
    # 4. Store assistant message in ConversationRepository
    # 5. Update session.turn_count
    # 6. Return (assistant_message, classification, reply_text)
```

**Session Updates:**
- `accumulated_extraction`: Merged with new extraction from this turn
- `latest_classification`: Latest bundle classification result
- `latest_recommendation`: Latest bundle recommendation
- `clarification_turn_count`: Incremented if clarification is needed

---

### PreviewFlow
**File:** `src/orchestrators/preview_flow.py`

Orchestrates the preview generation pipeline:

```python
def run(
    session_id: str,
    bundle_key: str,
    conversation_history: list[dict],
    extraction_result: ExtractionResult | None = None,
    preselected_intent: str | None = None,
) -> AppPayload:
    # 1. Call PreviewGeneratorService.generate()
    #    → runs 7-node LangGraph pipeline
    #    → returns (generation_json, dummy_data_json)
    # 2. Assemble AppPayload with display_name, modules list
    # 3. Return AppPayload
```

**Design Note:**
- `AppGeneratorService` is intentionally bypassed
- `AppGeneratorService.assemble()` loads `generation_json` from static disk templates and ignores preview data
- Our pipeline output becomes the source of truth

---

## Error Handling

**File:** `src/core/exceptions.py`

All routers catch domain exceptions and convert to HTTP responses:

| Exception | Status | Detail |
|-----------|--------|--------|
| `SessionNotFoundError` | 404 | "Session not found" |
| `BundleNotFoundError` | 404 | "Bundle not found" |
| `PreviewGenerationError` | 500 | Pipeline error details |
| `ValidationError` (Pydantic) | 422 | Field validation errors |
| Generic `Exception` | 500 | "Internal server error" |

**Key Validations:**
- Session exists before any operation
- Session confirmed before preview generation (except early preview)
- Bundle key is valid (known to catalog)
- Conversation history is non-empty before preview (at least one user message)

---

## Middleware

### AuthMiddleware
**File:** `src/api/middleware/auth.py`

- Validates Bearer token in `Authorization` header
- Optional in debug mode
- Sets `request.state.user_id` on authenticated requests

### RateLimitMiddleware
**File:** `src/api/middleware/rate_limit.py`

- Per-endpoint quotas
- Per-session rolling window
- Returns 429 if exceeded

### CORS
- **Debug mode:** Allow all origins
- **Production:** Allow only configured origins (default: empty)

---

## Data Flow Summary

```
User Request (HTTP)
    ↓
FastAPI Router
    ├─ Validate request schema
    ├─ Dependency injection (get_*_repository, get_*_service)
    └─ Call orchestrator (ConversationFlow, PreviewFlow)
        ├─ Invoke agents (InterpreterService, PreviewGeneratorService, etc.)
        ├─ Update repositories (SessionRepository, ConversationRepository)
        └─ Assemble response (AppPayload, SessionResponse)
    ↓
Response Schema
    ↓
HTTP Response (JSON)
```

---

## Configuration

**File:** `src/core/config.py`

Key settings:
- `DEBUG` — Enable debug logging, CORS, mock endpoints
- `PORT` — Server port (default: 8000)
- `BUNDLE_REGISTRY_PATH` — Path to bundle_registry.yaml
- `TEMPLATES_DIR` — Path to template bundles
- `LLM_PROVIDER` — "openai" or "anthropic"
- `ENABLE_MOCK_ENDPOINTS` — Enable `/mock` routes

---

## Testing

**Integration Tests:**
- `tests/integration/test_dev_a_to_preview_handoff.py` — Session → conversation → preview
- `tests/integration/test_preview_generator_flow.py` — Pipeline end-to-end
- `tests/integration/test_early_preview.py` — Unconfirmed preview with fallback
- `tests/unit/api/test_preview_router.py` — Router validation

**Key Test Fixtures:**
- `create_session_with_history()` — Session with N conversation turns
- `mock_interpreter_service` — Returns hardcoded classifications
- `mock_preview_flow` — Returns canned preview payloads

---

## Performance Notes

- **Session/Conversation Repositories:** In-memory (O(1) lookup by ID)
- **Bundle Catalog:** Cached on startup, revalidated per request
- **Preview Pipeline:** ~500ms-2s depending on LLM calls (if enabled)
- **LLM Calls:** Optional per node, rate-limited globally and per-session

---

## Security

- **Input Sanitization:** User text stripped of HTML/script tags before LLM injection
- **SQL Injection:** N/A (in-memory stores, no SQL queries)
- **Token Validation:** All endpoints (except health) require valid auth token
- **Rate Limiting:** Global + per-session quotas on preview endpoints

See also: `docs/architecture/` for threat models and security decisions.
