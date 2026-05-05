# Preview, App Generator, and Endpoint Improvement Plan

## Summary

Audit result: focused tests currently pass (`175 passed`) and template validation passes, so this is a stabilization/alignment plan rather than an emergency bug fix.

Main goal: make preview generation, final app generation, mock endpoints, and session/preview endpoints use one consistent bundle identity model and one predictable payload contract.

After every implementation, please append your changes and decisions to this file in rootdir: changes_2026-04-30-changelogs.md 

## Key Changes

- Standardize bundle identity across preview, app generation, and endpoints:
  - Public/API `bundle_key` should be the canonical catalog key: `hr_management`, `finance`, `healthcare`, etc.
  - `render_key` should remain internal compatibility metadata, not the top-level API identity.
  - Update preview output so `payload.bundle_key`, `generation_json.bundle_key`, and `dummy_data_json.bundle_key` all use the canonical key.
  - Preserve legacy render-key validation only as backward compatibility, not as the primary output shape.

- Fix final app generation to consume current preview payloads safely:
  - Extend `GenerateAppRequest` with optional `generation_json`.
  - If `generation_json` is supplied, final `/sessions/{id}/app` should validate and package the client's preview output instead of reloading static `app.json`.
  - If omitted, keep the current static-template path as legacy fallback.
  - Expand app-generator schema dispatch so catalog keys that share render profiles validate through the correct compatible schema instead of failing or forcing `render_key`.

- Improve preview pipeline consistency:
  - Remove the early-preview `all_microservices -> generic -> all_microservices` response rewrite.
  - Run the pipeline directly with `all_microservices` when no confident bundle exists.
  - When static dashboard widgets are injected, rebuild or update `dashboard_generation_output` so widget counts match the injected widgets.
  - Keep bundle-template and dashboard enrichment best-effort in production, but surface a structured warning in preview responses when overlay/enrichment is missing or degraded.

- Improve endpoint behavior:
  - Add explicit handling for `PreviewGenerationError` and `InvalidPayloadError` in preview/app routes with clear 422/500 responses.
  - Validate selected bundle keys before running preview/app flows and return 404 for unknown catalog keys.
  - Consolidate health routing into one router module and remove the unused duplicate health router path.
  - Move early-preview bundle resolution policy into a small helper/service so route code and tests share one policy.

- Improve mock endpoints:
  - Accept canonical bundle keys as the primary mock path keys.
  - Keep legacy render-key aliases only when unambiguous.
  - For ambiguous render keys like `project_mgmt` and `ticketing`, return a 400 with the valid canonical bundle keys instead of silently choosing the first catalog match.

## Public API / Type Changes

- `GenerateAppRequest` adds optional `generation_json: dict[str, object] | None`.
- Preview and app responses continue using `AppPayloadResponseSchema`.
- Canonical `bundle_key` becomes the expected value in top-level payloads, `generation_json`, and `dummy_data_json`.
- Mock endpoints prefer canonical bundle keys; ambiguous render-key use returns a client error.

## Test Plan

- Update/add unit tests for:
  - Preview output bundle-key consistency.
  - Early preview direct `all_microservices` fallback.
  - Dashboard widget injection updating `dashboard_generation_output`.
  - App generator finalizing with supplied preview `generation_json`.
  - Legacy app generator static path still working.
  - Mock canonical key resolution and ambiguous render-key rejection.
  - Endpoint error mapping for invalid payloads and preview failures.

- Run focused verification:
  - `poetry run pytest tests/unit/orchestrators/test_preview_flow.py tests/unit/preview_generator tests/unit/app_generator tests/unit/api -q`
  - `poetry run pytest tests/integration/test_early_preview.py tests/integration/test_classifier_to_preview_flow.py tests/integration/test_preview_edit_flow.py tests/integration/test_preview_generator_flow.py tests/integration/test_sessions_api.py -q`
  - `python scripts/validate_templates.py`

- Final verification:
  - `make ci-preflight`
  - `make ci-preflight-full` if time allows.

## Assumptions

- Canonical catalog keys are now the source of truth for API-facing identity.
- Existing render-key behavior is compatibility support, not the desired future contract.
- No new dependencies are needed.
- The AI Bundle Classifier and Replier do not need changes for this work.
