# Feature Implementation Document

## 1. Feature Overview

**Feature Name:** Create Bundle Metadata Mapping

**Short Description:**

Create the structured mapping layer that links each supported bundle to its associated modules, KPIs, entities, workflows, and onboarding configuration requirements for downstream preview and app configuration.

**Business Purpose:**

This feature provides the configuration metadata needed after bundle selection so the system can understand what a chosen bundle should contain. It acts as the canonical mapping between a selected bundle and the functional components required to generate onboarding-ready configuration and bundle-specific previews.

**Problem It Solves:**

Selecting a bundle is not enough by itself. Once a bundle is recommended, the system still needs to know what should be configured for that bundle, such as:

- which modules are included
- which entities are relevant
- which workflows should be represented
- which KPIs should appear
- which onboarding configuration data is required

Without Bundle Metadata Mapping, downstream components would have no consistent way to translate bundle selection into app structure, preview content, and onboarding requirements. This feature solves that by defining structured metadata mappings for every supported bundle.

---

## 2. Scope

### In Scope

- Define structured mappings from bundle IDs to:
    - modules
    - KPIs
    - entities
    - workflows
    - onboarding configuration metadata
- Support canonical metadata lookup for each supported bundle
- Provide machine-readable metadata for downstream consumers such as:
    - Preview Generator
    - App Generator
    - onboarding configuration flows
- Support bundle-specific terminology where relevant
- Support bundle-specific configuration dependencies and required fields
- Support version-controlled and maintainable metadata definitions
- Allow future expansion of bundle metadata without changing the core architecture

### Out of Scope

- Bundle classification itself
- Confidence scoring
- Recommendation logic
- Clarification generation
- Template fetching
- Template modification
- Final FE rendering
- Backend provisioning logic itself
- Runtime generation of new metadata mappings for unsupported bundles

### Limitations

- Metadata mappings apply only to supported predefined bundles
- Mapping quality depends on the accuracy of bundle design and onboarding requirements
- MVP mappings are expected to be manually curated
- Cross-bundle composition may be limited in MVP
- Metadata mapping does not decide whether a bundle is correct; it only describes what that bundle contains and requires

---

## 3. Business Rules

1. Every supported bundle must have a structured metadata mapping.
2. Bundle Metadata Mapping must act as the canonical source of truth for what a selected bundle includes.
3. Each bundle mapping must define, at minimum, the relevant:
    - modules
    - entities
    - workflows
    - KPIs
4. Each bundle mapping must support downstream onboarding configuration requirements.
5. Metadata mappings must use unique and stable bundle IDs that align with the bundle registry.
6. Unsupported bundles must not resolve to production metadata mappings.
7. Modules mapped to a bundle must be relevant to that bundle’s intended workflow.
8. KPIs mapped to a bundle must reflect meaningful metrics for preview or onboarding configuration.
9. Entities mapped to a bundle must reflect the business objects that the app is expected to manage.
10. Workflows mapped to a bundle must reflect the expected business process supported by that bundle.
11. Metadata mappings must be machine-readable and deterministic.
12. Metadata mappings must not contain user-session-specific runtime data.
13. User-specific information may personalize templates later, but must not replace static bundle metadata mappings.
14. If a bundle mapping is incomplete, invalid, or missing required sections, it must fail validation and not be treated as production-ready.
15. Metadata mappings must be maintainable by engineering and understandable to product stakeholders.
16. Changes to bundle metadata mappings must be version-controlled and reviewed.
17. Downstream systems must be able to consume bundle metadata without reinterpreting bundle intent from scratch.

---

## 4. User Flow / Workflow

### User-Facing Workflow

1. User describes the app or workflow they want.
2. The system extracts structured signals and classifies the request into a supported bundle.
3. Once a bundle is selected or recommended, the system looks up the corresponding Bundle Metadata Mapping.
4. The mapping tells the system:
    - which modules belong to the bundle
    - which entities should be represented
    - which workflows should be configured
    - which KPIs may be surfaced
    - what onboarding configuration structure is needed
5. Downstream services use this metadata to prepare preview generation and app configuration.

### Internal Workflow

1. Receive selected or recommended bundle ID from upstream classification/recommendation logic.
2. Load bundle metadata mapping using the canonical registry or metadata file.
3. Validate the mapping structure.
4. Return structured metadata to downstream services.
5. Use metadata to support:
    - preview structure
    - dummy data shaping
    - app payload configuration
    - onboarding requirements
6. Preserve mapping consistency across bundle updates and releases.

---

## 5. Acceptance Criteria

1. Each supported bundle has a machine-readable metadata mapping.
2. Each metadata mapping includes modules, entities, workflows, and KPIs.
3. Metadata mappings align with the canonical bundle registry.
4. Metadata mappings can be retrieved deterministically by bundle ID.
5. The system can use bundle metadata to support downstream onboarding configuration.
6. The Preview Generator can consume metadata to understand what should be represented in the preview.
7. The App Generator can consume metadata to understand what should be included in the final configuration payload.
8. Invalid or incomplete mappings fail validation.
9. Metadata mappings are version-controlled and documented.
10. Unit and integration tests cover bundle-to-metadata lookup and validation.
11. Metadata mappings can be extended for new supported bundles without breaking the architecture.

---

## 6. Security Considerations

- Bundle metadata mappings must be treated as controlled internal configuration data.
- Only authorized contributors should be allowed to modify bundle metadata definitions.
- Metadata mappings must not contain sensitive runtime user data.
- Changes to metadata mapping files must go through review and validation.
- If mappings are exposed through internal APIs, only the required metadata should be returned.
- File resolution and metadata loading paths must be validated to avoid invalid or unsafe configuration access.

---

## 7. Timeline

| Phase | Duration | Dates |
| --- | --- | --- |
| Phase 1 – Metadata Schema Design | 1–2 days | TBD |
| Phase 2 – MVP Bundle Metadata Authoring | 2–3 days | TBD |
| Phase 3 – Validation and Lookup Integration | 1–2 days | TBD |
| Phase 4 – Downstream Consumer Alignment | 1–2 days | TBD |
| Phase 5 – Testing and Review | 1–2 days | TBD |

---

## 8. Task Breakdown per Phase

| Phase | Task | Estimate | Owner | Notes |
| --- | --- | --- | --- | --- |
| Phase 1 | Define metadata mapping schema | 0.5–1 day | JR | Must align with onboarding and preview needs |
| Phase 1 | Define required metadata sections | 0.5 day | JR / PM | Modules, KPIs, entities, workflows, config requirements |
| Phase 1 | Align bundle IDs with canonical registry | 0.5 day | JR | Avoid mapping drift |
| Phase 2 | Create metadata mapping for MVP bundles | 1–2 days | JR | Example: HR, CRM, Ticketing, Inventory |
| Phase 2 | Define module and workflow lists per bundle | 0.5–1 day | JR / PM | Ensure business relevance |
| Phase 2 | Define KPI and entity mappings per bundle | 0.5–1 day | JR | Used for preview/config support |
| Phase 2 | Define onboarding configuration requirements | 0.5–1 day | JR / PM | Required fields, labels, dependencies |
| Phase 3 | Implement metadata loading and lookup logic | 0.5–1 day | JR | Deterministic bundle-to-metadata resolution |
| Phase 3 | Implement metadata validation | 0.5–1 day | JR | Fail on incomplete or invalid mappings |
| Phase 4 | Align metadata output with Preview Generator | 0.5 day | JR / CJ | Ensure preview structure compatibility |
| Phase 4 | Align metadata output with App Generator | 0.5 day | JR / CJ | Ensure config payload compatibility |
| Phase 5 | Create unit tests for metadata lookup and validation | 0.5 day | JR | Core config integrity |
| Phase 5 | Create integration tests with bundle recommendation and preview flow | 0.5–1 day | JR | Validate end-to-end use |
| Phase 5 | Review and approval | 0.5 day | PM / Tech Lead | Final signoff |

---

## 9. Other Documents

| Document Title | Description | Link |
| --- | --- | --- |
| Project Stitch System Overview | Overall architecture and component responsibilities | TBD |
| Bundle Information Feature Doc | Canonical bundle definitions and mappings | TBD |
| Bundle Recommendation Logic Feature Doc | Upstream source of selected bundle | TBD |
| Preview Generator Feature Doc | Uses metadata to build bundle-specific previews | TBD |
| App Generator Feature Doc | Uses metadata to build final configuration payloads | TBD |
| Contracts Documentation | Shared schemas for bundle metadata and downstream consumers | TBD |

---

## 10. Change Logs

| Version | Date | Author | Description of Change | Approved By |
| --- | --- | --- | --- | --- |
| 0.1 | TBD | Lars / JR | Initial draft | TBD |
| 0.2 | TBD | TBD | Added onboarding configuration and structured metadata mapping guidance | TBD |
| 1.0 | TBD | TBD | Approved MVP version | TBD |

# Planner