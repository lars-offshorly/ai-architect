# Agents — Codemap

**Last Updated:** 2026-04-13

## Overview

The system comprises four specialized agents:

1. **Interpreter Agent** (Dev A) — Conversation analysis + bundle classification
2. **Replier Agent** (Dev A) — Generate clarification responses
3. **Preview Generator Agent** (Dev B) — Generate personalized workspace preview
4. **App Generator Agent** (Dev C) — Provision Knit workspace from preview config

This map covers agents 1, 2, and 4. Agent 3 (Preview Generator) has its own detailed map in `pipeline.md`.

---

## Interpreter Agent (Dev A)

**Location:** `src/agents/interpreter/`

### Purpose
Analyze user message to classify the bundle (business domain) the user is describing.

### Service

**File:** `src/agents/interpreter/service.py`

```python
class InterpreterService:
    def __init__(
        self,
        bundle_keys: list[str],  # All known bundle keys from catalog
        catalog: BundleCatalog,
    ):
        self._bundle_keys = bundle_keys
        self._catalog = catalog
        self._llm_client = get_llm_client()  # OpenAI or Anthropic
    
    def classify(
        self,
        conversation_history: list[dict],
        accumulated_extraction: ExtractionResult | None = None,
    ) -> tuple[ClassificationResult, ExtractionResult]:
        """Analyze conversation and return bundle classification + extraction."""
        # 1. Extract business context (keywords, people, teams, etc.)
        # 2. Classify into bundle categories
        # 3. Generate ranked candidates with confidence scores
        # 4. Return ClassificationResult + ExtractionResult
```

**Inputs:**
- `conversation_history` — All messages (user + assistant) up to current turn
- `accumulated_extraction` — Previous extraction (for merging)

**Outputs:**
- `ClassificationResult` — Selected bundle, alternatives, confidence, status
- `ExtractionResult` — Extracted personalization signals (company, roles, departments, etc.)

### Classification Process

**Phase 1 (Current):** Heuristic keyword matching + LLM extraction
**Phase 2 (Planned):** Full LLM classification with in-context learning

**Confidence Status:**
| Status | Confidence | Next Step |
|--------|-----------|-----------|
| proceed | > 0.8 | Show preview with selected bundle |
| suggest_alternatives | 0.6-0.8 | Offer alternatives |
| clarify | < 0.6 | Ask clarification question |
| fallback_generic | N/A | No signal; use generic |

### Extraction Fields

**PersonalizationSignals:**
- `company_name` — Company name mentioned in conversation
- `employee_names` — People mentioned as employees
- `role_names` — Job titles mentioned (e.g., "Attorney", "Developer")
- `department_names` — Departments mentioned
- `terminology` — Domain-specific terms (e.g., "matter" in legal, "sprint" in tech)

**ClassificationSignals:**
- `domain_hints` — Industry signals (legal, tech, healthcare, etc.)
- `workflow_hints` — Process signals (agile, waterfall, litigation, etc.)
- `metrics` — KPI terminology mentioned (on-time, sla, capacity, headcount, etc.)

### Integration with Preview Pipeline

The Interpreter output is passed to the preview pipeline:

```
Interpreter.classify(history)
    ↓
ClassificationResult + ExtractionResult
    ↓
Session.latest_classification = ClassificationResult
Session.accumulated_extraction = ExtractionResult  (merged)
    ↓
PreviewFlow.run(extraction_result=session.accumulated_extraction)
    ↓
extract_user_context node maps ExtractionResult → UserContext (Tier 1)
```

**Key Benefit:** No redundant LLM extraction inside preview pipeline.

---

## Replier Agent (Dev A)

**Location:** `src/agents/replier/`

### Purpose
Generate helpful assistant responses during conversation, including clarification questions.

### Service

**File:** `src/agents/replier/service.py`

```python
class ReplierService:
    def generate_reply(
        self,
        conversation_history: list[dict],
        classification_result: ClassificationResult,
    ) -> str:
        """Generate an assistant response based on classification context."""
        # If confidence_status == "clarify":
        #   Generate question based on missing_context
        # Else:
        #   Generate confirmation/encouragement message
        # Return reply text
```

**Inputs:**
- `conversation_history` — Full conversation to date
- `classification_result` — Latest classification (to understand context)

**Output:**
- `reply_text` — Assistant message

### Reply Logic

**If Clarification Needed (confidence < 0.6):**
```
missing_context = ["team_size", "work_methodology"]
→ "I understand you work in {domain}. 
   To refine my recommendation, could you tell me:
   1. How many people are on your team?
   2. Do you use Agile or Waterfall processes?"
```

**If Confident (confidence > 0.8):**
```
→ "Great! Based on what you've shared, 
   I'm recommending the {bundle_name} workspace. 
   This includes {key_features}. 
   Please confirm this is right for you."
```

**If Medium Confidence (0.6-0.8):**
```
→ "I'm thinking {primary_bundle} might be the best fit,
   but {alternative_bundle} could also work depending on {detail}.
   Which sounds more like your situation?"
```

### Integration with Conversation Flow

```
ConversationFlow.process_turn(session_id, user_message)
    ├─ Interpreter.classify(history)
    │   ↓ ClassificationResult
    └─ Replier.generate_reply(history, classification_result)
        ↓
        Assistant message stored in ConversationRepository
```

---

## Preview Generator Agent (Dev B)

**Full Details:** See `docs/CODEMAPS/pipeline.md`

### Quick Overview

**Location:** `src/agents/preview_generator/`

**Service:** `PreviewGeneratorService`

**Function:** Transform bundle key + conversation history → workspace preview JSON

**Pipeline:** 7-node LangGraph DAG:
1. extract_user_context
2. resolve_bundles_to_flags
3. select_data_tier
4. generate_sample_data
5. build_kpi_metrics
6. validate_schema
7. emit_preview

**Output:** `(generation_json, dummy_data_json)`
- generation_json — Knit workspace config (69 feature flags, modules, config)
- dummy_data_json — Sample data stores (employees, projects, tickets, weaves)

**Key Innovation:** Personalization from conversation context without re-running classification LLM.

---

## App Generator Agent (Dev C)

**Location:** `src/agents/app_generator/`

### Purpose
Provision an actual Knit workspace from the preview configuration.

### Service

**File:** `src/agents/app_generator/service.py`

```python
class AppGeneratorService:
    def __init__(
        self,
        template_repository: TemplateRepository,
        bundle_catalog: BundleCatalog,
    ):
        self._templates = template_repository
        self._catalog = bundle_catalog
    
    def generate(
        self,
        session_id: str,
        bundle_key: str,
        generation_json: dict,
        dummy_data_json: dict,
    ) -> dict:
        """Provision workspace using template + preview data."""
        # 1. Load bundle template (app.json)
        # 2. Merge generation_json and dummy_data_json
        # 3. Validate against Knit schema
        # 4. Return provisioning result
```

**Inputs:**
- `generation_json` — Feature flags, modules, config from preview
- `dummy_data_json` — Sample data stores
- `bundle_key` — To select template

**Output:**
- Provisioning result (workspace_id, status, metadata)

### Design Decisions

**Why separate from Preview?**
- Preview is fast (100-300ms), deterministic, no LLM
- App provisioning is slow (2-5s), calls Knit APIs, may require polling
- Different deployment models: Preview runs in API server; provisioning may be async job queue

**Template Strategy:**
- Each bundle has a static `src/templates/bundles/{bundle_key}/app.json`
- Template defines module structure, default data relationships
- Preview pipeline output is merged into template for final workspace

**No Mutual Dependency:**
- Dev B (Preview Generator) doesn't depend on Dev C
- Dev C reads the output of Dev B (AppPayload)
- Can iterate independently

---

## Agent Composition

### Conversation Flow

**File:** `src/orchestrators/conversation_flow.py`

Composes Interpreter + Replier for a single turn.

```python
class ConversationFlow:
    def __init__(
        self,
        interpreter_service: InterpreterService,
        replier_service: ReplierService,
        bundle_catalog: BundleCatalog,
        required_slots_by_bundle: dict[str, list[str]],
    ):
        self._interpreter = interpreter_service
        self._replier = replier_service
        self._catalog = bundle_catalog
        self._required_slots = required_slots_by_bundle
    
    def process_turn(
        self,
        session_id: str,
        user_message: str,
        previous_extracted: ExtractionResult | None = None,
    ) -> tuple[ConversationMessage, ClassificationResult, str]:
        """Process a conversation turn."""
        # 1. Store user message
        # 2. Call Interpreter (classify + extract)
        # 3. Check if clarification needed (missing_context, confidence < 0.8)
        # 4. Call Replier (generate response)
        # 5. Store assistant message
        # 6. Update Session with classification + extraction
        # 7. Return (assistant_message, classification, reply_text)
```

**Session Updates:**
```python
session.accumulated_extraction = merge(previous, new_extraction)
session.latest_classification = new_classification
session.turn_count += 1
```

### Preview Flow

**File:** `src/orchestrators/preview_flow.py`

Composes Preview Generator + App Payload assembly.

```python
class PreviewFlow:
    def __init__(
        self,
        preview_generator_service: PreviewGeneratorService,
        bundle_display_names: dict[str, str],
    ):
        self._preview_gen = preview_generator_service
        self._display_names = bundle_display_names
    
    def run(
        self,
        session_id: str,
        bundle_key: str,
        conversation_history: list[dict],
        extraction_result: ExtractionResult | None = None,
        preselected_intent: str | None = None,
    ) -> AppPayload:
        """Generate preview and assemble AppPayload."""
        # 1. Call PreviewGeneratorService.generate()
        # 2. Assemble AppPayload with display_name and modules
        # 3. Return AppPayload (ready for HTTP response or app provisioning)
```

---

## Agent Communication Contracts

### Interpreter → Replier

```python
ClassificationResult = {
    "selected_bundle": BundleSuggestion,
    "confidence_status": "proceed" | "clarify" | "suggest_alternatives",
    "missing_context": ["team_size", "industry", ...],
    "reasoning": "Based on mentions of X and Y...",
}
```

Replier uses `confidence_status` and `missing_context` to decide what question to ask.

### Interpreter → Preview Generator

```python
ExtractionResult = {
    "company_name": "Acme Corp",
    "employee_names": ["Alice", "Bob"],
    "role_names": ["Attorney", "Paralegal"],
    "department_names": ["Corporate", "Litigation"],
    "domain_hints": ["legal"],
    "workflow_hints": ["waterfall"],
    "metrics": ["billable_hours", "case_load"],
}
```

Preview generator uses this to create `UserContext` without re-running extraction LLM.

### Preview Generator → App Generator

```python
AppPayload = {
    "generation_json": {
        "feature_flags": [...69 flags...],
        "modules": ["HRHub", "Dashboard", "KPI"],
        "config": {...bundle-specific config...},
    },
    "dummy_data_json": {
        "stores": {
            "employees": [...],
            "tickets": [...],
            "projects": [...],
            "weaves": [...],
        },
    },
}
```

App generator merges this with static template and provisions workspace.

---

## Service Dependency Injection

**File:** `src/api/deps.py`

All agents are cached and injected:

```python
@lru_cache(maxsize=1)
def get_interpreter_service() -> InterpreterService:
    return InterpreterService(
        bundle_keys=catalog.list_keys(),
        catalog=catalog,
    )

@lru_cache(maxsize=1)
def get_replier_service() -> ReplierService:
    return ReplierService()

@lru_cache(maxsize=1)
def get_preview_generator_service() -> PreviewGeneratorService:
    return PreviewGeneratorService(get_bundle_catalog())

@lru_cache(maxsize=1)
def get_app_generator_service() -> AppGeneratorService:
    return AppGeneratorService(
        template_repository=get_template_repository(),
        bundle_catalog=get_bundle_catalog(),
    )
```

---

## Testing Strategy

### Unit Tests

**Interpreter:**
- `tests/unit/agents/interpreter/test_classify.py` — Classification logic
- `tests/unit/agents/interpreter/test_extract.py` — Extraction logic

**Replier:**
- `tests/unit/agents/replier/test_generate_reply.py` — Reply generation

**Preview Generator:**
- `tests/unit/preview_generator/` — 7 node tests + edit sub-graph

**App Generator:**
- `tests/unit/app_generator/test_service.py` — Template merging
- `tests/unit/app_generator/test_validators.py` — Schema validation

### Integration Tests

**End-to-End Flow:**
- `tests/integration/test_dev_a_to_preview_handoff.py` — Session → Interpreter → Preview
- `tests/integration/test_classifier_to_preview_flow.py` — Classifier output → preview
- `tests/integration/test_early_preview.py` — Unconfirmed preview with fallback

**Agent Composition:**
- `tests/integration/test_conversation_flow.py` — Interpreter + Replier turn
- `tests/integration/test_preview_generator_flow.py` — 45+ scenarios for preview pipeline

---

## Performance Characteristics

| Agent | Time | LLM Calls | Notes |
|-------|------|-----------|-------|
| Interpreter (classify) | 100-500ms | 1-2 | LLM cost; can be cached |
| Replier | 50-200ms | 1 | Generate reply |
| Preview Generator | 100-300ms | 0 (current) | No LLM; deterministic |
| App Generator | 2-5s | 0 | API calls to Knit |

**Total Session Flow:** ~1-2 seconds per turn (interpreter + replier)
**Total Preview:** ~300ms-1s (preview gen + app payload assembly)

---

## Future Enhancements (Phase 2+)

### Interpreter Agent
- [ ] LLM-based classification with in-context learning
- [ ] Multi-turn dialogue management (track conversation state)
- [ ] Dynamic clarification question generation
- [ ] Industry-specific extraction keywords

### Replier Agent
- [ ] Tone adaptation (professional, casual, technical)
- [ ] Personalized responses based on user history
- [ ] Proactive suggestions based on patterns

### Preview Generator Agent
- [ ] Tier 2 LLM-enhanced data generation (niche industries)
- [ ] Per-session LLM call counter (max 3)
- [ ] Advanced edit sub-graph with fuzzy matching

### App Generator Agent
- [ ] Async provisioning with status polling
- [ ] Workspace customization templates
- [ ] Rollback/undo capability
- [ ] Cost estimation

---

## Architecture Decisions

### Why Separate Agents?
- **Single Responsibility:** Each agent does one thing well
- **Independent Development:** Dev A, B, C can work in parallel
- **Scalability:** Easy to async queue or microservice later
- **Testing:** Each agent independently testable

### Why No Mutual Dependencies?
- **Decoupling:** Agents can be versioned independently
- **Flexibility:** Can swap implementations without cascading changes
- **Error Isolation:** Failure in one agent doesn't block others

### Why Conversation Context in Preview?
- **Personalization:** Preview can be context-aware without re-classification
- **Performance:** Avoids redundant LLM calls
- **Consistency:** Uses same extraction as conversation flow

### Why Edit Sub-graph (Phase 2)?
- **User Control:** Allow edits without full re-generation
- **Fast Iteration:** ~50ms per edit vs ~300ms full pipeline
- **Stateless:** No session re-run needed
