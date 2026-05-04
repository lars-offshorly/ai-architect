# Feature Implementation Document

## 1. Feature Overview

**Feature Name:** Develop Bundle Classifier & Confidence Scorer

**Short Description:**

Build the classification and ranking component that maps extracted keywords, contextual signals, entities, intents, and workflow hints to predefined supported bundles, then assigns confidence scores to determine how certain the system is about the predicted bundle selection.

**Business Purpose:**

This feature enables the system to move from structured conversational understanding into a deterministic bundle decision. It provides the bridge between upstream signal extraction and downstream template selection by identifying the most appropriate supported bundle for the user’s request.

**Problem It Solves:**

After the system extracts structured signals from conversation history and the latest user input, it still needs a reliable way to determine which supported bundle best matches the request. Without a bundle classifier, downstream systems would either need to interpret raw signals independently or rely on weak heuristics. This feature solves that by ranking candidate bundles, selecting a primary bundle, and scoring how confident the system is in that selection so it can either proceed or trigger clarification when certainty is too low.

---

## 2. Scope

### In Scope

- Consume structured output from the Keyword and Signal Extraction Pipeline
- Map extracted signals to predefined supported bundles
- Rank multiple candidate bundles
- Select a primary bundle for downstream use
- Generate confidence scores for bundle predictions
- Support threshold-based decision logic for:
    - proceed with selected bundle
    - request clarification
    - surface alternative candidate bundles
- Support bundle classification using:
    - entities
    - intents
    - workflow hints
    - domain hints
    - metrics
    - synonyms / alternate phrases
- Support use of deterministic rules and model-assisted reasoning where appropriate
- Return machine-readable bundle ranking output for downstream systems

### Out of Scope

- Raw keyword extraction
- Summarization
- Clarification generation itself
- Template fetching
- Template modification
- Preview JSON generation
- Final FE payload generation
- Backend provisioning
- Arbitrary runtime generation of new bundles

### Limitations

- Classification quality depends on the quality of extracted signals
- Weak or ambiguous requests may still require clarification
- MVP classification supports only predefined bundles
- Multi-bundle composition is not the primary MVP behavior
- Industry may be used as a supporting hint, but bundle selection should primarily depend on workflow, entities, and intents

---

## 3. Business Rules

1. The Bundle Classifier must consume structured extracted signals rather than raw user conversation as its primary input.
2. The classifier must map requests only to predefined supported bundles.
3. Bundle classification must prioritize:
    - workflow type
    - entities
    - intents
    - metrics
    over industry labels alone.
4. Industry may be used as a secondary hint for ranking when relevant, but not as the primary classifier axis.
5. The classifier must support multiple candidate bundles and rank them in order of relevance.
6. The classifier must return one primary selected bundle for MVP downstream processing.
7. Each candidate bundle must include a confidence or score value.
8. Confidence scores must be used to determine whether the system should:
    - proceed with classification
    - ask clarification questions upstream
    - surface alternative bundle candidates
9. If classification confidence is below the configured threshold, the system must not silently overcommit to a bundle without allowing clarification logic upstream.
10. The classifier must support synonyms and alternate phrasing through Bundle Information or classification rules.
11. The classifier must allow ranked bundle suggestions to change over the course of the conversation as new signals are extracted.
12. Candidate bundles should be modeled as ordered, mutable ranked outputs.
13. The classifier must not directly fetch templates or generate preview data.
14. The classifier must output a normalized machine-readable structure for downstream consumers.
15. Unsupported requests must not be forced into unrelated bundles without low-confidence handling.
16. Classification logic should combine deterministic rules and structured reasoning where appropriate.
17. Thresholds for classification certainty should be configurable.
18. The classifier must support use by the broader Interpreter layer, not as an isolated standalone UI feature.

---

## 4. User Flow / Workflow

### User-Facing Workflow

1. User describes the app, workflow, or system they want in natural language.
2. The Keyword and Signal Extraction Pipeline processes the latest user input and relevant conversation history.
3. Structured signals are passed into the Bundle Classifier.
4. The classifier evaluates the extracted signals against the supported bundle registry.
5. The classifier ranks possible candidate bundles.
6. A confidence score is assigned to each candidate bundle.
7. If confidence is strong enough, the top-ranked bundle is selected for downstream template selection and preview generation.
8. If confidence is weak or missing critical context, the system routes to clarification through the Replier.
9. As the conversation continues, the classifier may update the ranked bundle suggestions based on newly extracted signals.

### Internal Workflow

1. Receive normalized extracted signals from the upstream extraction pipeline.
2. Load supported bundle definitions and classification rules.
3. Match extracted entities, intents, workflow hints, and other signals against bundle metadata.
4. Generate a ranked list of bundle candidates.
5. Assign a confidence score to each candidate.
6. Compare the top candidate score against the configured threshold.
7. Return:
    - selected bundle
    - ranked candidates
    - confidence scores
    - confidence status / proceed-or-clarify signal
8. Persist or expose the classification result for downstream services.

---

## 5. Acceptance Criteria

1. The classifier can consume structured extracted signals from the upstream extraction pipeline.
2. The classifier can map extracted signals to predefined supported bundles.
3. The classifier returns a ranked list of candidate bundles.
4. The classifier selects one primary bundle for MVP downstream flow.
5. Each bundle candidate includes a confidence score.
6. The classifier supports configurable threshold logic for certainty.
7. Low-confidence classifications can be surfaced for clarification rather than silent overcommitment.
8. The classifier supports use of entities, intents, workflow hints, and other extracted signals in bundle ranking.
9. Synonyms and alternate phrases can influence bundle matching when defined.
10. Bundle rankings can be updated as conversation context evolves.
11. The output is returned in a structured machine-readable schema.
12. Downstream systems can use the selected bundle and ranked candidates without reinterpreting raw user language.
13. Unit and integration tests cover representative supported bundle scenarios.
14. The classifier does not directly generate preview JSON or final payloads.

---

## 6. Security Considerations

- The classifier must only operate on session data relevant to the active conversation.
- Access to extracted signal state and classification results must be limited to authorized system components.
- Classification output must not expose internal-only debug metadata unless explicitly intended.
- Sensitive user-specific information used as part of signal interpretation must remain runtime/session data.
- Logs should avoid unnecessary exposure of raw conversation content or sensitive user-provided details.
- Classification thresholds and rules should be stored in controlled internal configuration, not editable by unauthorized users.
- If model-assisted ranking is used, prompts should avoid leaking irrelevant prior session data.

---

## 7. Timeline

| Phase | Duration | Dates |
| --- | --- | --- |
| Phase 1 – Classification Schema and Candidate Model Design | 1–2 days | TBD |
| Phase 2 – Bundle Matching Logic Implementation | 2–3 days | TBD |
| Phase 3 – Confidence Scoring and Threshold Logic | 1–2 days | TBD |
| Phase 4 – Conversation-State Update Handling | 1–2 days | TBD |
| Phase 5 – Testing and Evaluation | 2–3 days | TBD |
| Phase 6 – Documentation and Review | 1 day | TBD |

---

## 8. Task Breakdown per Phase

| Phase | Task | Estimate | Owner | Notes |
| --- | --- | --- | --- | --- |
| Phase 1 | Define classifier input and output schema | 0.5–1 day | JR | Must align with extraction pipeline and downstream consumers |
| Phase 1 | Define candidate bundle and confidence score models | 0.5 day | JR | Include ranked mutable suggestions |
| Phase 1 | Define threshold behavior for proceed vs clarify | 0.5 day | JR / PM | Important for user experience |
| Phase 2 | Implement signal-to-bundle matching logic | 1–2 days | JR | Use bundle registry metadata |
| Phase 2 | Implement synonym-aware bundle matching | 0.5–1 day | JR | Support alternate phrasing |
| Phase 2 | Implement ranked candidate generation | 0.5–1 day | JR | Top bundle should always be first |
| Phase 3 | Implement confidence scoring logic | 0.5–1 day | JR | Should support configurable threshold |
| Phase 3 | Implement low-confidence handling flags | 0.5 day | JR | Needed by Replier / Interpreter flow |
| Phase 4 | Implement update behavior across multi-turn conversation | 0.5–1 day | JR | Rankings may change as signals evolve |
| Phase 4 | Ensure classifier output remains stable and structured | 0.5 day | JR | Prevent downstream contract drift |
| Phase 5 | Create unit tests for bundle matching | 0.5–1 day | JR | Cover supported bundles and ambiguous prompts |
| Phase 5 | Create integration tests with extraction pipeline | 1 day | JR | Validate end-to-end classification behavior |
| Phase 5 | Evaluate confidence thresholds on sample conversations | 0.5–1 day | JR / PM | Tune certainty behavior |
| Phase 6 | Document classifier schema, scoring logic, and examples | 0.5 day | JR | For repo-wide context and maintenance |
| Phase 6 | Review and approval | 0.5 day | PM / Tech Lead | Final signoff |

---

## 9. Other Documents

| Document Title | Description | Link |
| --- | --- | --- |
| Project Stitch System Overview | Overall architecture and component responsibilities | TBD |
| Bundle Information Feature Doc | Supported bundles, metadata, and template mappings | TBD |
| Keyword and Signal Extraction Pipeline Feature Doc | Upstream signal extraction and normalization | TBD |
| AI Interpreter Feature Doc | Broader interpretation and coordination context | TBD |
| Replier Feature Doc | Clarification workflow when confidence is low | TBD |
| Preview Generator Feature Doc | Downstream template selection and modification | TBD |
| Contracts Documentation | Shared schemas across extraction, classification, and preview stages | TBD |

---

## 10. Change Logs

| Version | Date | Author | Description of Change | Approved By |
| --- | --- | --- | --- | --- |
| 0.1 | TBD | Lars / JR | Initial draft | TBD |
| 0.2 | TBD | TBD | Updated to reflect bundle/domain-first classification and confidence scoring | TBD |
| 1.0 | TBD | TBD | Approved MVP version | TBD |