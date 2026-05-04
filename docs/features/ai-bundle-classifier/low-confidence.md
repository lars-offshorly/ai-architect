| Low Confidence Fallback | If agents have low confidence score for results, trigger [action]TBD: *action for low-confidence scores* |
| --- | --- |

# Feature Implementation Document

## 1. Feature Overview

**Feature Name:** Low Confidence Fallback

**Short Description:**

Implement the fallback mechanism that activates when the system’s confidence in extracted signals, bundle classification, or downstream interpretation is too low to proceed safely. This feature determines the appropriate recovery action, such as triggering clarification through the Replier, surfacing uncertainty, or deferring final bundle selection until more information is collected.

**Business Purpose:**

This feature exists to prevent the system from making weak or misleading decisions when conversational understanding is uncertain. It ensures that the pipeline remains reliable, user-safe, and interpretable by introducing controlled behavior when confidence scores fall below the configured threshold.

**Problem It Solves:**

In natural-language interactions, users may provide incomplete, vague, conflicting, or ambiguous information. Without a low-confidence fallback, the system may incorrectly classify bundles, select the wrong templates, or generate previews based on weak assumptions. This feature solves that by defining what the system should do when certainty is not high enough to continue confidently.

---

## 2. Scope

### In Scope

- Define low-confidence detection behavior for upstream decision points
- Support threshold-based fallback when confidence is below acceptable levels
- Route low-confidence cases to the appropriate recovery path
- Trigger clarification through the Replier when missing or ambiguous information prevents safe progression
- Allow the system to defer final bundle selection when confidence is weak
- Support returning ranked alternative candidate bundles internally for downstream handling or clarification
- Expose machine-readable fallback status for orchestrators and downstream services
- Support configurable threshold values for low-confidence handling
- Support fallback based on:
    - bundle classification confidence
    - missing critical fields
    - conflicting extracted signals
    - ambiguous multi-turn conversation state

### Out of Scope

- Performing raw keyword extraction
- Generating clarification prompts directly
- Final bundle classification logic itself
- Template selection
- Template modification
- Preview JSON generation
- Backend provisioning
- Human review workflows unless added in future scope

### Limitations

- Fallback quality depends on the quality of upstream extracted signals and classification logic
- Low-confidence fallback cannot resolve ambiguity on its own; it only determines the correct next action
- MVP fallback is expected to route primarily to clarification, not advanced multi-path recovery
- Confidence thresholds may require tuning over time based on real usage

---

## 3. Business Rules

1. The system must not silently overcommit to a final bundle when confidence is below the configured threshold or at the start of the conversation.
2. Low-confidence handling must be treated as a normal part of the conversational workflow, not an exceptional crash state.
3. Confidence thresholds must be configurable rather than hardcoded throughout the system.
4. Low-confidence fallback may be triggered by:
    - low bundle classification confidence
    - missing critical fields
    - conflicting extracted signals
    - insufficient conversational context
5. If critical information is missing, the preferred fallback action for MVP must be clarification through the Replier.
6. If multiple candidate bundles are plausible but not clearly separable, the system may retain ranked alternatives internally while requesting clarification.
7. The fallback mechanism must return a structured status that downstream orchestrators can understand.
8. A low-confidence state must not proceed directly to template selection or preview generation unless explicitly allowed by business rules.
9. The system must preserve useful intermediate outputs, such as suggested bundle rankings, when entering fallback state.
10. The fallback logic must support multi-turn recovery, allowing the system to re-evaluate confidence after the user provides clarification.
11. The fallback action must be deterministic and documented for each supported low-confidence scenario.
12. Low-confidence fallback must not discard previously extracted structured state unless that state is explicitly invalidated.
13. Missing-field-based fallback should be preferred over generic “please clarify” behavior.
14. The fallback feature must support the broader Interpreter / Replier architecture rather than operate as a standalone feature.

---

## 4. User Flow / Workflow

### User-Facing Workflow

1. User sends a natural-language request.
2. The extraction pipeline and bundle classifier process the request.
3. The system evaluates whether confidence is high enough to proceed.
4. If confidence is sufficient, the system continues with normal downstream flow.
5. If confidence is too low, the Low Confidence Fallback feature determines the next action.
6. For MVP, the usual next action is:
    - trigger the Replier
    - ask targeted clarification questions based on missing or ambiguous fields
7. The user responds with additional information.
8. The system re-runs extraction and classification using the updated conversation context.
9. If confidence improves above threshold, normal flow resumes.

### Internal Workflow

1. Receive structured outputs from upstream extraction and classification components.
2. Evaluate confidence score against configured thresholds.
3. Check for:
    - missing critical fields
    - conflicting signals
    - weak separation between top-ranked bundle candidates
4. Determine fallback status.
5. Return a structured fallback decision such as:
    - proceed
    - clarify
    - defer bundle selection
6. If clarification is required, pass fallback context to the Replier.
7. Preserve ranked candidates and extracted state for the next turn.
8. Re-evaluate after user follow-up.

---

## 5. Acceptance Criteria

1. The system can detect when confidence is below the configured threshold.
2. The system can distinguish between:
    - high-confidence proceed state
    - low-confidence clarification state
    - deferred-selection state, if applicable
3. Low-confidence classification does not silently proceed to bundle finalization.
4. Missing critical information can trigger fallback even if some bundle signals are present.
5. The fallback feature returns structured output usable by orchestrators and the Replier.
6. Ranked bundle candidates can be preserved during fallback handling.
7. The Replier can use fallback output to generate targeted clarification prompts.
8. The system can re-run classification after fallback-triggered clarification.
9. Confidence threshold behavior is configurable.
10. Unit and integration tests cover ambiguous and low-confidence conversation examples.
11. The fallback mechanism does not break session state accumulation across turns.
12. Downstream template selection is blocked when fallback status is unresolved.

---

## 6. Security Considerations

- Low-confidence fallback must only operate on data within the active session context.
- Structured fallback state must be accessible only to authorized system components.
- Logs should avoid exposing unnecessary raw user content when recording low-confidence events.
- Fallback metadata should not expose sensitive internal scoring details to end users unless intentionally designed.
- Clarification prompts generated through fallback should use only relevant current-session information.
- Confidence thresholds and fallback rules should be stored in controlled internal configuration.

---

## 7. Timeline

| Phase | Duration | Dates |
| --- | --- | --- |
| Phase 1 – Fallback State Design | 1 day | TBD |
| Phase 2 – Threshold and Trigger Logic | 1–2 days | TBD |
| Phase 3 – Replier Integration | 1–2 days | TBD |
| Phase 4 – Multi-Turn Recovery Handling | 1 day | TBD |
| Phase 5 – Testing and Validation | 1–2 days | TBD |
| Phase 6 – Documentation and Review | 0.5–1 day | TBD |

---

## 8. Task Breakdown per Phase

| Phase | Task | Estimate | Owner | Notes |
| --- | --- | --- | --- | --- |
| Phase 1 | Define fallback states and output schema | 0.5 day | JR | Must support proceed vs clarify |
| Phase 1 | Define fallback triggers | 0.5 day | JR | Low confidence, missing fields, ambiguity |
| Phase 2 | Implement threshold evaluation logic | 0.5–1 day | JR | Use configurable thresholds |
| Phase 2 | Implement conflict / ambiguity detection | 0.5–1 day | JR | Example: close competing bundle scores |
| Phase 3 | Integrate fallback output with Replier | 0.5–1 day | JR | Missing fields should map to targeted clarification |
| Phase 3 | Ensure template-selection flow is blocked during unresolved fallback | 0.5 day | JR | Prevent premature preview generation |
| Phase 4 | Implement multi-turn fallback recovery handling | 0.5–1 day | JR | Re-evaluate after clarification |
| Phase 4 | Preserve ranked candidates and extracted state | 0.5 day | JR | Needed for conversation continuity |
| Phase 5 | Create unit tests for low-confidence scenarios | 0.5 day | JR | Weak signal, conflicting signals, missing info |
| Phase 5 | Create integration tests with Replier loop | 0.5–1 day | JR | Validate full recovery path |
| Phase 6 | Document fallback rules and examples | 0.5 day | JR | Repo-wide context and maintainability |
| Phase 6 | Review and approval | 0.5 day | PM / Tech Lead | Final signoff |

---

## 9. Other Documents

| Document Title | Description | Link |
| --- | --- | --- |
| Project Stitch System Overview | Overall architecture and component responsibilities | TBD |
| Keyword and Signal Extraction Pipeline Feature Doc | Upstream signal extraction and missing-field detection | TBD |
| Bundle Classifier & Confidence Scorer Feature Doc | Source of ranked bundle candidates and scores | TBD |
| Replier Feature Doc | Clarification generation for unresolved cases | TBD |
| Contracts Documentation | Shared fallback and confidence state schemas | TBD |
| Bundle Information Feature Doc | Supported bundles and bundle metadata | TBD |

---

## 10. Change Logs

| Version | Date | Author | Description of Change | Approved By |
| --- | --- | --- | --- | --- |
| 0.1 | TBD | Lars / JR | Initial draft | TBD |
| 0.2 | TBD | TBD | Added fallback states, threshold logic, and Replier integration | TBD |
| 1.0 | TBD | TBD | Approved MVP version | TBD |