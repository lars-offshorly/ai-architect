# Branch Review: `json-preview-generator-main` vs `internal-dev`

Generated: 2026-03-25

---

## Commits on This Branch

| SHA | Message |
|-----|---------|
| `720f179` | Review Fixes |
| `5fd1333` | feat: implement Phase 1 preview generator pipeline with Dev A integration |
| `7294eec` | changed gitignore |
| `618f2f2` | added important docs |

---

## File Summary

| Status | Count |
|--------|-------|
| Added  | 14    |
| Modified | 11  |
| Deleted  | 4   |

---

## Added Files

### New Pipeline Nodes (`src/agents/preview_generator/nodes/`)

| File | Lines | Purpose |
|------|-------|---------|
| `nodes/__init__.py` | 0 | Package marker |
| `nodes/data_tier.py` | 52 | Classifies the session into tier_1 / tier_3 based on bundle key |
| `nodes/emit.py` | 149 | Assembles `GenerationJson` + `DummyDataJson` and writes the final `PreviewOutput` to state |
| `nodes/extract_context.py` | 534 | Keyword-based extraction of `UserContext` from conversation history (company, industry, people, work type, etc.) |
| `nodes/kpi.py` | 105 | Selects relevant `KpiMetric` objects for the bundle |
| `nodes/resolve_flags.py` | 109 | Resolves feature flags from the bundle catalog into state |
| `nodes/sample_data.py` | 410 | Generates deterministic sample employees, projects, tickets, and weaves |
| `nodes/validate.py` | 95 | Validates the assembled output schema before emit |

### New Pipeline Wiring

| File | Lines | Purpose |
|------|-------|---------|
| `src/agents/preview_generator/pipeline.py` | 65 | Defines and compiles the LangGraph `StateGraph` connecting all nodes |

### New Tests

| File | Lines | Purpose |
|------|-------|---------|
| `tests/integration/test_dev_a_to_preview_handoff.py` | 460 | Integration tests for the Dev A → Preview handoff flow (session creation, confirm, preview call) |
| `tests/integration/test_preview_generator_flow.py` | 500 | End-to-end tests of the full preview generator pipeline across multiple bundles and conversation contexts |

### Other Added Files

| File | Purpose |
|------|---------|
| `Makefile` | Developer targets: `lint-mr`, `test`, `run`, etc. |
| `README.md` | Project documentation |

---

## Modified Files

### Core Pipeline

| File | Key Changes |
|------|-------------|
| `src/agents/preview_generator/schemas.py` | Added 5 new Pydantic models: `KpiMetric`, `GenerationConfig`, `GenerationJson`, `DummyDataJson`, `PreviewOutput`. Updated `Optional[X]` → `X \| None` throughout. |
| `src/agents/preview_generator/service.py` | **Complete rewrite.** Removed `TemplateRepository`/fetcher/modifier/injector dependencies. Now wraps the compiled LangGraph `compiled_graph` directly. `generate()` accepts `conversation_history: list[dict]` instead of `ExtractedInfo`. Returns `(generation_json, dummy_data_json)` dicts from the pipeline output. |
| `src/agents/preview_generator/state.py` | `kpi_metrics` typed from `list[dict]` → `list[KpiMetric]`. `output` typed from `Optional[dict]` → `Optional[PreviewOutput]`. |

### API Layer

| File | Key Changes |
|------|-------------|
| `src/api/deps.py` | `get_preview_generator_service()` no longer passes `TemplateRepository`. `get_preview_flow()` no longer passes `app_generator_service`. |
| `src/api/routers/preview.py` | Replaced `ExtractedInfo(session_id=...)` stub with real `conversation_history` from `ConversationRepository`. Removed `TemplateLoadError` handler. |
| `src/api/routers/session.py` | Added `bundle_key` persistence to session after both `start_session` and `reply_to_session` turns. |
| `src/api/__init__.py` | Removed `create_app` re-export (now imported directly by callers). |

### Orchestrator

| File | Key Changes |
|------|-------------|
| `src/orchestrators/preview_flow.py` | Removed `AppGeneratorService` dependency. `run()` now accepts `conversation_history` and builds `AppPayload` directly from pipeline output instead of delegating to `app_generator_service.assemble()`. |

### Config

| File | Key Changes |
|------|-------------|
| `pyproject.toml` | Added dev dependencies: `black`, `flake8`, `pylint`, `vulture`. Added `ruff` ignore rule for `B008` (FastAPI `Depends` pattern). Added full `[tool.pylint]` config block. |
| `.gitignore` | Updated ignores. |
| `requirements.txt` | Updated pinned dependencies. |

---

## Deleted Files

These files existed on `internal-dev` and have been removed:

| File | Lines | Reason |
|------|-------|--------|
| `src/agents/preview_generator/dummy_data.py` | 54 | Replaced by `nodes/sample_data.py` + `nodes/emit.py` |
| `src/agents/preview_generator/fetcher.py` | 34 | Template fetching no longer needed; data is generated programmatically |
| `src/agents/preview_generator/modifier.py` | 81 | Template modification logic removed; replaced by pipeline nodes |
| `src/agents/preview_generator/validators.py` | 35 | Replaced by `nodes/validate.py` (LangGraph node) |

---

## Architecture Change Summary

The branch replaces a **template-fetching** architecture with a **generative LangGraph pipeline**:

**Before (`internal-dev`)**
```
preview.py router → PreviewFlow → PreviewGeneratorService
                                    ├── TemplateFetcher (loads JSON from disk)
                                    ├── TemplateModifier (injects ExtractedInfo)
                                    ├── DummyDataInjector
                                    └── AppGeneratorService.assemble()
```

**After (this branch)**
```
preview.py router → PreviewFlow → PreviewGeneratorService
                                    └── compiled_graph.invoke(PreviewGeneratorState)
                                          ├── extract_user_context
                                          ├── resolve_data_tier
                                          ├── resolve_flags
                                          ├── generate_sample_data
                                          ├── build_kpi_metrics
                                          ├── validate_schema
                                          └── emit_preview
```

Key benefits:
- Conversation history is fully passed through and used for personalisation (previously a stub `ExtractedInfo` with no content was passed)
- No disk templates required; all data is generated programmatically
- Each stage is an isolated, testable LangGraph node
- `AppPayload` is built directly from typed pipeline output rather than via `AppGeneratorService`
