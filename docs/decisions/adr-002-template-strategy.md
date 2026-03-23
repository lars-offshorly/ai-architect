# ADR-002: Pre-Created Template Strategy

**Status:** Accepted
**Date:** 2026-03-23

## Context

Preview and app payloads need to reflect the user's business context. Options:
1. Generate JSON entirely from LLM at runtime
2. Use pre-created JSON templates with placeholder injection
3. Hybrid: LLM generates structure, templates provide defaults

## Decision

Use **pre-created JSON templates with placeholder injection** (`src/templates/bundles/`).

## Rationale

- Full LLM generation is unpredictable in schema shape and costly per request
- Templates guarantee a consistent, validated structure every time
- Placeholder injection (`{{company_name}}`, `{{employee_name}}`) personalises without LLM
- Templates are versioned and auditable — changes are visible in git diffs
- Scripts in `scripts/` support validating and seeding templates offline

## Consequences

- Every new bundle requires three files: `preview.json`, `app.json`, `dummy_data.json`
- `modifier.py` placeholder map must be updated when new personalisation fields are added
- `TemplateRepository` abstracts file access, making templates swappable in tests
