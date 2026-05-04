# Feature Implementation Document

## 1. Feature Overview

**Feature Name:** Build Bundle Recommendation Logic

**Short Description:**

Build the decision logic that converts classified bundle candidates and confidence scores into a recommended bundle outcome, including a primary bundle and optional fallback bundles for downstream use.

**Business Purpose:**

This feature translates classification output into a practical recommendation that the rest of the system can act on. It ensures the system can consistently identify the best-supported bundle while preserving ranked fallback options when certainty is weaker or ambiguity remains.

**Problem It Solves:**

The classifier may return multiple plausible bundles with varying confidence scores, but downstream systems need a clearer decision structure. Without bundle recommendation logic, each downstream component would need to decide for itself which bundle to trust, how to interpret low-confidence alternatives, and when to retain fallback options. This feature solves that by creating a standardized recommendation layer that produces:

- a primary recommended bundle
- optional fallback bundles
- recommendation status tied to confidence and ambiguity

---

## 2. Scope

### In Scope

- Consume ranked bundle candidates and confidence scores from the Bundle Classifier
- Select one primary recommended bundle
- Select one or more fallback bundles where appropriate
- Support confidence-aware recommendation logic
- Support recommendation outcomes such as:
    - proceed with primary bundle
    - proceed with primary bundle but retain fallbacks
    - defer recommendation pending clarification
- Preserve ranked fallback options for downstream use
- Return a structured recommendation result usable by orchestrators and downstream services
- Support configurable rules for:
    - number of fallback bundles
    - minimum score thresholds
    - acceptable score gaps between primary and fallback candidates

### Out of Scope

- Raw signal extraction
- Final bundle classification itself
- Clarification generation
- Template selection
- Template modification
- Preview JSON generation
- Final payload generation
- Backend provisioning
- Dynamic creation of new bundles

### Limitations

- Recommendation quality depends on the quality of upstream classification output
- Weak or conflicting candidate rankings may still require clarification upstream
- MVP recommendation logic is expected to support one primary bundle with limited fallback options
- Recommendation logic should not override upstream confidence handling without clear rules

---

## 3. Business Rules

1. Bundle Recommendation Logic must consume structured classification results rather than raw conversation input.
2. The feature must recommend one primary bundle for MVP whenever confidence and business rules allow.
3. The feature may retain one or more fallback bundles when downstream or clarification logic benefits from preserving alternatives.
4. Fallback bundles must remain ordered by rank.
5. The highest-ranked bundle should be selected as the primary recommendation when it meets the configured confidence and ambiguity requirements.
6. If the top candidate does not meet the required threshold, the recommendation logic must not force a primary recommendation without signaling low-confidence or deferred status.
7. Recommendation logic must consider both:
    - absolute confidence of the top bundle
    - relative separation between top bundle and fallback candidates
8. If the score gap between the top bundle and the next candidate is too small, the system may preserve fallback bundles and/or defer final recommendation depending on the configured rules.
9. Recommendation logic must support configurable limits such as:
    - maximum number of fallback bundles
    - minimum confidence threshold for primary recommendation
    - minimum score gap for confident recommendation
10. The feature must output a machine-readable recommendation structure.
11. Recommendation logic must not fetch templates or generate preview data directly.
12. Fallback bundles must be preserved in ranked order for future use in clarification or downstream recovery.
13. Recommendation logic must be able to update over multiple conversation turns as classification results change.
14. Unsupported bundles must not be recommended.
15. Recommendation logic must align with low-confidence fallback behavior and must not bypass clarification rules.

---

## 4. User Flow / Workflow

### User-Facing Workflow

1. User describes the app or workflow they want.
2. The extraction pipeline and Bundle Classifier process the request.
3. The classifier returns ranked candidate bundles with confidence scores.
4. Bundle Recommendation Logic evaluates the ranked results.
5. The system determines:
    - the primary recommended bundle
    - whether fallback bundles should be retained
    - whether confidence is sufficient to proceed
6. If confidence is strong, the primary bundle is used for downstream template selection.
7. If confidence is weaker or ambiguity remains, fallback bundles are preserved and the system may route to clarification.
8. As the conversation evolves, the recommendation can be recalculated with updated rankings.

### Internal Workflow

1. Receive ranked bundle candidates and associated confidence scores.
2. Check primary candidate against configured confidence threshold.
3. Check score gap between primary and next-ranked candidate(s).
4. Determine whether:
    - a primary recommendation can proceed
    - fallback bundles should be retained
    - recommendation should be deferred
5. Return a structured recommendation result containing:
    - primary bundle
    - fallback bundles
    - recommendation status
    - confidence context
6. Persist recommendation output in conversation/session state for reuse by downstream orchestrators.

---

## 5. Acceptance Criteria

1. The feature can consume ranked bundle candidates from the Bundle Classifier.
2. The feature can select one primary recommended bundle when confidence is sufficient.
3. The feature can retain one or more fallback bundles in ranked order.
4. Recommendation logic supports configurable thresholds and ranking rules.
5. The feature considers both top-bundle confidence and relative score separation.
6. Low-confidence or ambiguous cases do not silently force an unsafe recommendation.
7. The recommendation output is machine-readable and reusable by downstream components.
8. The recommendation can be updated across multiple turns as classification results evolve.
9. Unsupported bundles are not recommended.
10. Unit and integration tests cover:
    - high-confidence single-bundle recommendations
    - ambiguous top-two bundle scenarios
    - low-confidence deferred recommendations
11. Downstream systems can consume the recommendation output without reinterpreting raw classifier scores themselves.

---

## 6. Security Considerations

- Recommendation logic must only access classification results from the active session.
- Structured recommendation output must be accessible only to authorized internal system components.
- Logs should avoid exposing unnecessary raw user content or sensitive runtime details.
- Recommendation thresholds and ranking rules should be controlled through internal configuration.
- Fallback and ranking metadata exposed externally should be limited to what is needed for system behavior.

---

## 7. Timeline

| Phase | Duration | Dates |
| --- | --- | --- |
| Phase 1 – Recommendation Model Design | 1 day | TBD |
| Phase 2 – Recommendation Rule Implementation | 1–2 days | TBD |
| Phase 3 – Confidence / Gap Handling | 1 day | TBD |
| Phase 4 – State Integration | 1 day | TBD |
| Phase 5 – Testing and Validation | 1–2 days | TBD |
| Phase 6 – Documentation and Review | 0.5–1 day | TBD |

---

## 8. Task Breakdown per Phase

| Phase | Task | Estimate | Owner | Notes |
| --- | --- | --- | --- | --- |
| Phase 1 | Define recommendation output schema | 0.5 day | JR | Must include primary and fallback bundles |
| Phase 1 | Define recommendation status values | 0.5 day | JR | Example: proceed, proceed_with_fallbacks, defer |
| Phase 2 | Implement primary bundle selection logic | 0.5–1 day | JR | Use ranked classifier output |
| Phase 2 | Implement fallback bundle retention logic | 0.5 day | JR | Preserve order and top-k rules |
| Phase 3 | Implement confidence threshold checks | 0.5 day | JR | Must align with classifier thresholds |
| Phase 3 | Implement score-gap / ambiguity checks | 0.5 day | JR | Useful for close-ranked bundle cases |
| Phase 4 | Integrate recommendation output into session state | 0.5 day | JR | Needed for downstream orchestration |
| Phase 4 | Align recommendation logic with low-confidence fallback | 0.5 day | JR | Prevent bypass of clarification |
| Phase 5 | Create unit tests for recommendation scenarios | 0.5 day | JR | Cover strong, weak, ambiguous cases |
| Phase 5 | Create integration tests with classifier output | 0.5–1 day | JR | Ensure end-to-end recommendation consistency |
| Phase 6 | Document recommendation rules and examples | 0.5 day | JR | Repo-wide context and maintenance |
| Phase 6 | Review and approval | 0.5 day | PM / Tech Lead | Final signoff |

---

## 9. Other Documents

| Document Title | Description | Link |
| --- | --- | --- |
| Project Stitch System Overview | Overall architecture and component responsibilities | TBD |
| Bundle Classifier & Confidence Scorer Feature Doc | Upstream ranked candidate generation | TBD |
| Low Confidence Fallback Feature Doc | Clarification and deferred-decision behavior | TBD |
| Bundle Information Feature Doc | Supported bundles and metadata | TBD |
| Contracts Documentation | Shared schemas for classification and recommendation output | TBD |
| Preview Generator Feature Doc | Downstream consumer of primary recommended bundle | TBD |

---

## 10. Change Logs

| Version | Date | Author | Description of Change | Approved By |
| --- | --- | --- | --- | --- |
| 0.1 | TBD | Lars / JR | Initial draft | TBD |
| 0.2 | TBD | TBD | Added primary/fallback recommendation logic and confidence-aware rules | TBD |
| 1.0 | TBD | TBD | Approved MVP version | TBD |