# AI Architect — Blueprint

Repo: `ai-architect` (standalone)
Updated: 2026-04-20 · Author: Lars Lenon

Current priority: production preview generation flow — classify onboarding intent, select bundle + variant, run the LangGraph preview pipeline, overlay realistic `app-0*.json` fixtures, enrich dashboard widgets from static outputs, and return an `AppPayload` for workspace preview rendering.

## 1. What We're Building

AI-driven onboarding wizard: user describes what they need, the system interprets the business context, classifies the best bundle, selects a bundle variant, asks clarifying questions when confidence or required information is insufficient, then produces preview-ready workspace JSON.

We produce the JSON. Backend/API returns it.

| Decision | Answer |
| --- | --- |
| Client files? | No client-uploaded files in the main flow; preview data is generated from extraction signals, catalog metadata, and curated templates. |
| Code sharing with `ai-chat-bot`? | Same conventions (`JWT`, `pydantic-settings`, `.env`) — no shared imports. |
| Current priority | Conversation interpretation + preview generation with bundle variants and static dashboard output enrichment. |
| Legacy path | `AppGeneratorService.assemble()` is still available for older `/generate` paths, but `PreviewFlow` intentionally bypasses it. |
| RAG generator status | `src/generator/*` contains Pinecone-backed retrieval/personalisation primitives, but the operational preview path uses the LangGraph preview pipeline plus static bundle/dashboard templates. |

## 2. Architecture

Two-stage pipeline:

1. Conversation and interpretation — `ConversationFlow.process_turn()` runs summarisation, extraction, classification, deterministic variant selection, missing-field checks, fallback handling, and bundle confirmation.
2. Preview generation — `PreviewFlow.run()` runs the LangGraph preview pipeline, overlays the selected bundle variant template, enriches dashboards from static outputs, and assembles the final `AppPayload`.

```text
User message
  │
  ▼
ConversationFlow.process_turn()
  ├── Summarizer                         compress history
  ├── InterpreterService.interpret()
  │     ├── Extractor                    LLM structured extraction
  │     ├── Classifier                   LLM bundle scores + deterministic rule boosts
  │     └── VariantSelector              deterministic app-01/app-02/app-03 selection
  ├── MissingFieldDetector / Replier      clarification if required
  ├── FallbackHandler                     confidence thresholds and generic fallback
  └── BundleRecommendationService         final bundle recommendation
  │
  ▼ status: "ready_for_preview"
    bundle_key + variant_key + ExtractionResult + slots
  │
  ▼
PreviewFlow.run()
  ├── PreviewGeneratorService.generate()  LangGraph pipeline
  ├── _apply_bundle_template()            overlay src/templates/bundles/{bundle}/app-0*.json stores
  ├── _enrich_dashboard_widgets()         dashboard_output_templates/*.json (static)
  └── AppPayload                          final preview payload
```

## 3. Graph Nodes

### Conversation Stage

| Component | Purpose | Output |
| --- | --- | --- |
| `Summarizer` | Compress prior conversation when history is available. | Summary text |
| `Extractor` | LLM-based structured extraction of keywords, entities, intents, workflow hints, domain hints, and metrics. | `ExtractionResult` |
| `SignalAccumulator` | Merge current extraction with accumulated session extraction. | Updated `ExtractionResult` |
| `Classifier` | LLM scores each bundle key, then deterministic signal boosts are applied with `detect_signals()` / `apply_rule_boosts()`. | `ClassificationResult` with ranked candidates |
| `VariantSelector` | Pure deterministic scoring of the selected bundle's variants against extracted signals. | `variant_key` on `BundleSuggestion` and `ExtractionResult.bundle_variant_key` |
| `MissingFieldDetector` / `ReplierService` | Ask for missing required fields or ambiguous bundle variants. | Clarification message |
| `FallbackHandler` | Apply confidence thresholds, max clarification turns, and generic fallback rules. | Confidence/fallback route |
| `BundleRecommendationService` | Produce final bundle recommendation. | Confirmable bundle suggestion |

### Preview LangGraph Stage

Pipeline definition: `src/agents/preview_generator/pipeline.py`

```text
extract_user_context
  → resolve_bundles_to_flags
  → select_data_tier
  → generate_sample_data
  → build_kpi_metrics
  → validate_schema
      ├─ valid or retries exhausted → emit_preview → END
      └─ invalid, retries remain    → resolve_bundles_to_flags
```

| Node | Purpose | Output |
| --- | --- | --- |
| `extract_user_context` | Convert `ExtractionResult` and conversation history into preview context. | `UserContext` |
| `resolve_bundles_to_flags` | Resolve catalog bundle to Knit feature flags, modules, permissions, and landing pages. | Generation config fields |
| `select_data_tier` | Choose sample-data depth based on available context. | Data tier |
| `generate_sample_data` | Generate sample operational stores for the selected bundle. | `dummy_data_json.stores` |
| `build_kpi_metrics` | Generate KPIs and dashboard-related metrics. | KPI stores |
| `validate_schema` | Validate pipeline output and retry when possible. | Validation route |
| `emit_preview` | Emit final `PreviewOutput`. | `generation_json`, `dummy_data_json` |

## 4. Key Schemas

### `ExtractionResult`

Condensed shape used across the interpreter and preview pipeline:

```python
class ExtractionResult(BaseModel):
    keywords: list[str]
    entities: list[str]
    intents: list[str]
    workflow_hints: list[str]
    domain_hints: list[str]
    metrics: list[str]
    missing_fields: list[MissingFieldType]
    bundle_variant_key: str | None
```

### `BundleSuggestion` / `ClassificationResult`

```python
class BundleSuggestion(BaseModel):
    bundle_key: str
    display_name: str
    confidence: float
    reasoning: str
    matched_signals: list[str]
    variant_key: str | None
    variant_confidence: float | None

class ClassificationResult(BaseModel):
    session_id: str
    selected_bundle: BundleSuggestion | None
    ranked_candidates: list[BundleSuggestion]
    confidence_status: str
    top_confidence: float
    score_gap: float
    reasoning: str
```

### `PreviewOutput`

`PreviewGeneratorService.generate()` returns:

```python
tuple[generation_json: dict, dummy_data_json: dict, user_context: UserContext | None]
```

### `AppPayload`

`PreviewFlow.run()` assembles the final payload directly:

```python
AppPayload(
    session_id=session_id,
    bundle_key=bundle_key,
    display_name=display_name,
    modules=modules,
    generation_json=generation_json,
    dummy_data_json=dummy_data_json,
)
```

### Output JSONs Condensed

`generation_json` — Knit workspace config the backend consumes:

```json
{
  "schema_version": "1.0",
  "session_id": "uuid",
  "bundle": "hr_management",
  "modules": ["hr_hub", "chat", "video_call", "kpi"],
  "feature_flags": ["hrhub-module", "dashboard-module"],
  "config": {
    "permissions": ["hr_hub", "kpi"],
    "landing_pages": []
  }
}
```

`dummy_data_json` — sample preview stores:

```json
{
  "schema_version": "1.0",
  "session_id": "uuid",
  "bundle": "hr_management",
  "stores": {
    "employees": [],
    "tickets": [],
    "kpis": [],
    "dashboard_widgets": [],
    "dashboard_generation_output": {}
  }
}
```

## 5. Bundle Catalog

The bundle catalog is the canonical source for classification and orchestration metadata.

Source: `src/templates/bundle_registry.yaml`
Loader/model: `catalog/bundle_catalog.py`

```python
class BundleVariantDefinition(BaseModel):
    key: str                      # app-01, app-02, app-03
    display_name: str
    description: str = ""
    is_default: bool = False
    keywords: list[str]
    anti_keywords: list[str]
    typical_entities: list[str]
    typical_intents: list[str]
    industry_hints: list[str]
    dashboard_template: str | None
    clarification_label: str = ""

class BundleDefinition(BaseModel):
    bundle_key: str
    render_key: str
    display_name: str
    primary_entity: str
    description: str
    template_dir: str
    default_modules: list[str]
    optional_modules: list[str]
    knit_service_bundles: list[str]
    required_slots: list[str]
    flags: list[str]
    permission_services: list[str]
    landing_pages: list[dict]
    synonyms: list[str]
    typical_entities: list[str]
    typical_intents: list[str]
    signal_boosts: dict[str, float]
    variants: list[BundleVariantDefinition]
```

| Bundle | Render Key | Default Modules | Required Slots | Variant Templates |
| --- | --- | --- | --- | --- |
| `hr_management` | `hr_hub` | `hr_hub`, `chat`, `video_call`, `kpi`, `rewards_store`, `weaves` | `team_size`, `primary_use_case` | `app-01`, `app-02`, `app-03` |
| `project_mgmt` / `project_ops` | project workspace | catalog-defined project modules | catalog-defined required slots | `app-01`, `app-02`, `app-03` where present |
| `ticketing` | ticketing workspace | catalog-defined ticketing modules | catalog-defined required slots | `app-01`, `app-02`, `app-03` where present |
| `finance` | finance/project render path | catalog-defined finance modules | catalog-defined required slots | `app-01`, `app-02`, `app-03` |
| `marketing` | marketing/project render path | catalog-defined marketing modules | catalog-defined required slots | `app-01`, `app-02`, `app-03` |
| `sales` | sales/project render path | catalog-defined sales modules | catalog-defined required slots | `app-01`, `app-02`, `app-03` |
| `healthcare` | healthcare/ticketing render path | catalog-defined healthcare modules | catalog-defined required slots | `app-01`, `app-02`, `app-03` |
| `legal_services` | legal/ticketing render path | catalog-defined legal modules | catalog-defined required slots | `app-01`, `app-02`, `app-03` |
| `construction` | construction/project render path | catalog-defined construction modules | catalog-defined required slots | `app-01`, `app-02`, `app-03` |
| `real_estate` | real estate/project render path | catalog-defined real-estate modules | catalog-defined required slots | `app-01`, `app-02`, `app-03` |
| `education` | education/project render path | catalog-defined education modules | catalog-defined required slots | `app-01`, `app-02`, `app-03` |
| `all_microservices` | full platform | catalog-defined full-platform modules | catalog-defined required slots | `app-01`, `app-02`, `app-03` |
| `generic` | generic | generic fallback modules | minimal fallback slots | `app-01`, `app-02`, `app-03` |

Notes:

- `hr_hub` is added as a legacy alias for `hr_management` when the default catalog is loaded.
- Registry metadata owns classification/orchestration fields.
- JSON template files own renderable static fixture content.
- If registry fields and template fields overlap, registry wins for orchestration and template wins for rendered stores.

## 6. Preview Data Generator (Current Operational Path)

### Why This Path

| Approach | Status |
| --- | --- |
| Pure LLM data generation | Too non-deterministic for stable previews. |
| Fully hardcoded output | Stable but inflexible and poor at reflecting user context. |
| Current hybrid path | LangGraph generates base config/KPIs; curated bundle variant templates provide realistic operational stores; dashboard service generates widgets. |
| RAG generator | Available in `src/generator`, but not the main `PreviewFlow` path. |

### Stage 1 — Conversation & Interpretation

`InterpreterService` runs:

1. `Extractor` — LLM structured extraction of keywords, entities, intents, workflow hints, domain hints, and metrics.
2. `Classifier` — LLM bundle scores plus deterministic rule boosts from registry signals.
3. `VariantSelector` — deterministic scoring of a selected bundle's `variants`; writes `variant_key` such as `app-01`, `app-02`, or `app-03`.

`ConversationFlow.process_turn()` orchestrates clarification, confirmation, fallback, and returns `status: "ready_for_preview"` with `bundle_key`, `variant_key`, `ExtractionResult`, and slots once ready.

### Stage 2 — Preview Pipeline (LangGraph)

Orchestrator: `PreviewFlow.run()`
Service: `PreviewGeneratorService.generate()`
Pipeline: `src/agents/preview_generator/pipeline.py`

Outputs:

- `generation_json` — Knit workspace config: feature flags, modules, permissions, landing pages, and config.
- `dummy_data_json` — generated sample stores.
- `user_context` — extracted business context used by post-pipeline enrichment steps.

### Stage 3 — Bundle Template Overlay (`app-0*.json`)

After the pipeline completes, `PreviewFlow._apply_bundle_template()` uses `BundleTemplateLoader` to:

1. Load the matching variant file from `src/templates/bundles/{bundle_key}/`.
2. Resolve by `variant_key`; fall back to `app-01` when missing or unknown.
3. Overlay the template's `stores` into `dummy_data_json["stores"]`.
4. Skip dashboard-owned store keys: `dashboard_widgets` and `dashboard_generation_output`.

This replaces generic operational stores with curated, domain-specific fixtures while preserving pipeline-owned dashboard stores.

### Stage 4 — Dashboard Enrichment

`PreviewFlow._enrich_dashboard_widgets()` does:

1. `StaticDashboardOutputRegistry.get_widgets(bundle_key, variant_key)` resolves the correct pre-generated `dashboard_output_templates/*.json` payload.
2. `dummy_data_json["stores"]["dashboard_widgets"]` is populated from the static payload.

All dashboard enrichment failures are swallowed. The preview still returns with `dashboard_widgets: []` when static output resolution fails.

### Stage 5 — Final Assembly

`PreviewFlow.run()` builds `AppPayload` directly from the pipeline result and post-processing mutations.

`AppGeneratorService.assemble()` is intentionally bypassed here because it loads `generation_json` from static disk templates and ignores pipeline output. It remains for legacy code paths, including older `/generate` flows, where it normalizes dummy data, validates schemas, and backfills `dashboard_generation_output`.

### RAG Generator Inventory

The RAG-backed generator primitives live under `src/generator/`:

| File | Purpose |
| --- | --- |
| `retriever.py` | Fetches bundle/industry templates from Pinecone namespace `templates`, with fallback IDs `{bundle}__{industry}`, `{bundle}__base`, `generic__base`. |
| `personaliser.py` | Merges retrieved template sections and uses structured LLM output to produce `GenerationJSON` + `DummyDataJSON`. |
| `schemas.py` | Defines retrieved template metadata and generator output schemas. |
| `validator.py` | Validates generated modules and non-empty stores against `BundleCatalog`. |

The original RAG blueprint referenced `data_generator/`, `bundle_templates`, and `seed_templates.py`; those paths are not the current implemented preview path in this repository.

## 7. Transport & Streaming

Primary API flow:

```text
POST /sessions
POST /sessions/{id}/reply
POST /sessions/{id}/confirm
POST /sessions/{id}/preview
```

Current documented preview path is request/response JSON through FastAPI routers. The blueprint target for streaming remains SSE (`text/event-stream`) with structured events such as `token`, `interrupt`, `bundle_suggestion`, and `complete`, but the current architecture overview should treat preview assembly as synchronous unless the route implementation explicitly streams.

## 8. Security & NFRs

| Concern | Approach |
| --- | --- |
| Secrets | Environment variables via `pydantic-settings`; no hardcoded API keys. |
| Auth | JWT middleware in `src/api/middleware/auth.py`. |
| Prompt injection | Structured system/user prompt separation; sanitization utilities live in `src/core/sanitize.py`. |
| Rate limiting | API middleware in `src/api/middleware/rate_limiter.py`. |
| LLM temperatures | Classifier uses `CLASSIFIER_TEMPERATURE`; conversational/report/assembler paths use their configured temperatures. |
| Logging | Structured session-aware logging via `core.logging` and `get_session_logger()`. |
| Preview resilience | Bundle overlay and dashboard enrichment are best-effort; failures are logged and do not block returning the base preview. |
| Validation | Preview pipeline validates schema and retries; legacy/RAG generator validators validate modules and stores. |

## 9. Directory Structure

```text
ai-architect/
├── catalog/
│   └── bundle_catalog.py                  # bundle + variant registry loader/models
├── dashboard_output_templates/            # pre-generated dashboard widget outputs
├── docs/
│   └── architecture/
│       └── system_overview.md
├── src/
│   ├── api/
│   │   ├── app.py
│   │   ├── deps.py                        # DI wiring
│   │   ├── middleware/                    # auth.py, rate_limiter.py
│   │   └── routers/                       # session.py, preview.py, app.py, bundles.py, health.py
│   ├── agents/
│   │   ├── interpreter/
│   │   │   ├── service.py                 # InterpreterService
│   │   │   ├── extractor.py               # LLM extraction
│   │   │   ├── classifier.py              # LLM scores + rule boosts
│   │   │   ├── rules.py                   # detect_signals/apply_rule_boosts
│   │   │   ├── variant_selector.py        # deterministic app-0* selection
│   │   │   ├── missing_fields.py
│   │   │   ├── fallback.py
│   │   │   └── summarizer.py
│   │   ├── preview_generator/
│   │   │   ├── pipeline.py                # LangGraph definition
│   │   │   ├── service.py                 # PreviewGeneratorService
│   │   │   ├── state.py
│   │   │   ├── schemas.py
│   │   │   ├── nodes/                     # extract, flags, data tier, sample data, KPI, validate, emit
│   │   │   ├── bundle_template_loader.py  # app-0*.json overlay loader
│   │   │   └── dashboard/
│   │   │       ├── static_output_registry.py   # static widget output resolver
│   │   │       └── templates.py                # compatibility registry over static outputs
│   │   ├── app_generator/                 # legacy assemble path
│   │   └── replier/                       # clarification and bundle suggestion messages
│   ├── core/                              # settings, llm, logging, database, pinecone, sanitize
│   ├── domain/                            # shared models, enums, services
│   ├── generator/                         # RAG/Pinecone generator primitives, not main PreviewFlow path
│   ├── orchestrators/
│   │   ├── conversation_flow.py           # conversation orchestration
│   │   └── preview_flow.py                # preview orchestration + final AppPayload
│   ├── repositories/                      # sessions, conversation, templates, data stash
│   └── templates/
│       ├── bundle_registry.yaml           # canonical bundle catalog
│       ├── feature_flags.yaml
│       ├── metrics_catalog.yaml
│       └── bundles/                       # app.json, app-01.json, app-02.json, app-03.json
└── tests/
    ├── unit/
    └── integration/
```

## 10. Key Files Summary

| Component | File |
| --- | --- |
| Conversation orchestrator | `src/orchestrators/conversation_flow.py` |
| Interpreter service | `src/agents/interpreter/service.py` |
| Extractor | `src/agents/interpreter/extractor.py` |
| Classifier | `src/agents/interpreter/classifier.py` |
| Rule boosts | `src/agents/interpreter/rules.py` |
| Variant selector | `src/agents/interpreter/variant_selector.py` |
| Replier / clarification | `src/agents/replier/service.py` |
| Bundle catalog | `catalog/bundle_catalog.py` |
| Bundle registry | `src/templates/bundle_registry.yaml` |
| Preview orchestrator | `src/orchestrators/preview_flow.py` |
| LangGraph pipeline definition | `src/agents/preview_generator/pipeline.py` |
| Preview generator service | `src/agents/preview_generator/service.py` |
| Bundle template loader | `src/agents/preview_generator/bundle_template_loader.py` |
| Bundle variant fixtures | `src/templates/bundles/{bundle}/app-0*.json` |
| Static dashboard output registry | `src/agents/preview_generator/dashboard/static_output_registry.py` |
| Dashboard output payloads | `dashboard_output_templates/*.json` |
| App generator legacy path | `src/agents/app_generator/service.py` |
| RAG retriever | `src/generator/retriever.py` |
| RAG personaliser | `src/generator/personaliser.py` |
| RAG validator | `src/generator/validator.py` |
| DI wiring | `src/api/deps.py` |
