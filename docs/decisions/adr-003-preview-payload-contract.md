# ADR-003: Preview Payload Contract

**Status:** Accepted
**Date:** 2026-03-23

## Context

The frontend needs a stable, predictable JSON contract for rendering the workspace preview. The contract must cover both the configuration structure and the dummy data.

## Decision

The final payload is split into two top-level keys: `generation_json` and `dummy_data_json`, wrapped in `AppPayloadResponseSchema`.

```json
{
  "schema_version": "1.0",
  "session_id": "...",
  "bundle_key": "hr_hub",
  "display_name": "HR Hub",
  "modules": [...],
  "generation_json": { "config": { ... }, "modules": [...] },
  "dummy_data_json": { "stores": { "tickets": [...], "kpis": [...] } }
}
```

## Rationale

- Separating config from data mirrors the frontend's need: config drives UI layout, data populates stores
- `schema_version` allows backward-compatible evolution
- `AppPayloadContract.validate_contract()` enforces required keys at assembly time
- Transport schema (`api/schemas/app_payload.py`) is kept separate from domain model (`domain/models/app_payload.py`) to allow independent evolution

## Consequences

- FE must handle both `generation_json` and `dummy_data_json` in every response
- Adding new stores requires updating `dummy_data.json` templates and the contract validator
- `schema_version` must be bumped on breaking changes
