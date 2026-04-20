# AI Architect Codemaps — Index

**Last Updated:** 2026-04-13

This directory contains architectural maps of the AI Architect codebase, organized by functional domain. Each codemap is generated directly from source code to ensure accuracy and relevance.

---

## Codemaps

### [Backend Architecture](./backend.md)
FastAPI application structure, HTTP routers, API contracts, and orchestrators.
- API routes (`/sessions`, `/preview`, `/bundles`, `/app`)
- Request/response schemas
- Dependency injection
- Session and conversation repositories
- Error handling

### [Preview Generator Pipeline](./pipeline.md)
The 7-node LangGraph pipeline that generates personalized workspace previews.
- State machine definition
- Node implementations (extract, resolve, sample, validate, emit)
- Bundle resolution and feature flag logic
- KPI metric generation
- Edit sub-graph (parse/apply)

### [Database & Domain Models](./database.md)
Core data models and repositories for sessions, conversations, and bundles.
- Session model (state machine, persistent fields)
- Conversation messages
- Domain models (AppPayload, ExtractionResult, ClassificationResult)
- In-memory repositories
- Bundle and catalog models

### [Agents](./agents.md)
Three independent agents that compose the onboarding pipeline.
- Interpreter Agent (Dev A) — conversation + bundle classification
- Replier Agent — clarification responses
- Preview Generator Agent (Dev B) — preview generation
- App Generator Agent (Dev C) — workspace provisioning

### [External Integrations](./integrations.md)
External services, LLMs, vector databases, and middleware.
- LLM services (OpenAI, Anthropic)
- Vector database (Pinecone)
- Auth middleware
- Rate limiting
- Logging and monitoring

---

## Architectural Quick Links

| Layer | File Path | Responsibility |
|-------|-----------|-----------------|
| **API Entry** | `src/api/app.py` | FastAPI app factory, middleware, router mounting |
| **API Routes** | `src/api/routers/{session,preview,bundles,app}.py` | HTTP endpoints, validation, error handling |
| **Core Pipeline** | `src/agents/preview_generator/pipeline.py` | 7-node LangGraph DAG |
| **Pipeline State** | `src/agents/preview_generator/state.py` | Working memory for pipeline execution |
| **Pipeline Nodes** | `src/agents/preview_generator/nodes/*.py` | Context extraction, flag resolution, data generation, validation, emit |
| **Orchestrators** | `src/orchestrators/{conversation,preview}_flow.py` | Service composition, error handling, state transitions |
| **Domain Models** | `src/domain/models/*.py` | Session, conversation, bundles, payloads, classifications |
| **Repositories** | `src/repositories/*.py` | In-memory stores for sessions, conversations, templates |
| **Bundle Catalog** | `src/catalog/bundle_catalog.py` | Bundle registry, feature flags, extraction keywords, metrics |

---

## Data Flow Diagrams

### Session Lifecycle
```
Create Session
  ↓
POST /sessions/{id}/reply (conversation turn)
  ├─ Interpreter Service (bundle classification)
  ├─ Replier Service (clarification)
  └─ Store ConversationMessage
  ↓
POST /sessions/{id}/confirm (user confirms bundle)
  └─ Set Session.confirmed = True, selected_bundle_key
  ↓
POST /sessions/{id}/preview (early or confirmed)
  └─ PreviewFlow → PreviewGeneratorService
      └─ 7-node LangGraph pipeline
      └─ AppPayload (generation_json + dummy_data_json)
  ↓
POST /sessions/{id}/app (workspace provisioning)
  └─ AppGeneratorService → Knit workspace
```

### Preview Pipeline (7 nodes)
```
extract_user_context
  ↓ (company, industry, people, teams from conversation)
resolve_bundles_to_flags
  ↓ (enable flags for selected bundle)
select_data_tier
  ↓ (Tier 1: known, Tier 3: fallback)
generate_sample_data
  ↓ (employees, projects, tickets, weaves)
build_kpi_metrics
  ↓ (KPI list from bundle defaults + context signals)
validate_schema
  ├─ [valid] → emit_preview → END
  └─ [invalid, retries remain] → resolve_bundles_to_flags (retry)
```

---

## Technology Stack

- **Framework:** FastAPI 0.100+
- **Graph Orchestration:** LangGraph 0.0.x
- **Data Validation:** Pydantic v2
- **Language:** Python 3.10+
- **Testing:** pytest, pytest-asyncio
- **Async Runtime:** asyncio
- **Vector DB:** Pinecone (for embeddings, optional)
- **LLM:** OpenAI, Anthropic (pluggable)

---

## Key Concepts

### Three-Agent Pipeline
1. **Interpreter Agent** (Dev A) — Classifies user intent, extracts context from conversation
2. **Preview Generator Agent** (Dev B) — Generates personalized workspace preview JSON
3. **App Generator Agent** (Dev C) — Provisions actual Knit workspace from preview config

### Preview Generation Tiers
- **Tier 1:** Known bundle key (hr_management, project_mgmt, ticketing) — full feature flags + personalized sample data
- **Tier 2:** (Phase 2) Niche industry or LLM-enhanced data generation
- **Tier 3:** Unknown bundle — generic fallback with minimal flags

### Edit Flow (Phase 2)
- `parse_edit_instruction()` — NLP → EditAction (add/remove module, KPI, dashboard)
- `apply_edit()` — JSON mutation with cascading effects (removing a module removes its KPIs and sample data)

---

## Repository Layout

```
src/
├── api/
│   ├── app.py                    # FastAPI factory, middleware
│   ├── deps.py                   # Dependency injection
│   ├── routers/                  # HTTP routes
│   ├── routes/                   # Health check
│   ├── schemas/                  # Pydantic request/response models
│   └── middleware/               # Auth, rate limiting
├── agents/
│   ├── interpreter/              # Dev A — classification
│   ├── replier/                  # Dev A — clarifications
│   ├── preview_generator/        # Dev B — main focus
│   │   ├── nodes/                # 7 pipeline nodes
│   │   ├── edit/                 # Phase 2 — edit flow
│   │   ├── bundles/              # Feature flags registry
│   │   ├── state.py              # LangGraph state
│   │   ├── schemas.py            # Internal domain models
│   │   ├── pipeline.py           # Compiled graph
│   │   └── service.py            # Wrapper service
│   └── app_generator/            # Dev C — provisioning
├── domain/
│   ├── models/                   # Core data classes
│   ├── enums/                    # Bundle types, intent types
│   └── services/                 # Domain logic (bundle resolution, metadata)
├── orchestrators/
│   ├── conversation_flow.py      # Conversation orchestration
│   └── preview_flow.py           # Preview orchestration
├── repositories/                 # In-memory stores
├── catalog/                      # Bundle catalog, metrics
├── core/                         # Config, logging, exceptions
├── templates/                    # Bundle-specific app.json files
└── generator/                    # (Legacy utilities)
```

---

## Related Documentation

- **Feature Docs:** `docs/features/`
  - `preview_generator.md` — Implementation plan
  - `ai_interpreter.md` — Classification agent
  - `app_generator.md` — Workspace provisioning

- **Architecture Decisions:** `docs/decisions/`
  - ADR-001: Bundle classification strategy
  - ADR-002: Template strategy
  - ADR-003: Preview payload contract

- **Architecture Overview:** `docs/architecture/`
  - `system_overview.md` — High-level system design
  - `sequence_flow.md` — Request/response flows
  - `contracts.md` — Data contracts between agents

---

## Update Frequency

Codemaps are regenerated when:
- Major features are added or removed
- API routes change
- Pipeline node implementations significantly change
- Data model structures change

Minor bug fixes and internal refactoring do NOT trigger codemap updates unless they materially affect the architecture.

---

Generated from source code. Not a specification document — use this as a reference guide to the actual implementation.
