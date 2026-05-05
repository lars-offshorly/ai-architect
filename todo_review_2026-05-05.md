# To-Do Review - May 5, 2026

## Summary

This review covers the current state after the broad `app-0*.json` template updates under `src/templates/bundles/` and the static dashboard output integration under `dashboard_output_templates/`.

The good news: the core backend template and dashboard variant mapping is largely in place. The catalog knows all 13 canonical bundles, each bundle has 3 app variants, and every catalog variant resolves to a dashboard output template. `scripts/validate_templates.py` also passes.

The remaining work is mostly integration polish around API response contracts, frontend controls, mock/demo paths, and validation. The biggest practical gap is that `/mock/{bundle_key}` currently bypasses `PreviewFlow`, so it does not test the exact template overlay and dashboard enrichment path that production previews use.

## Inputs Reviewed

- Root changelogs: `changes_2026-04-10.md`, `changes_2026-04-14.md`, `changes_2026-04-15.md`, `changes_2026-04-17.md`, `changes_2026-04-20.md`, `changes_2026-04-27.md`, `changes_2026-04-30-1.md`, `changes_2026-04-30-2.md`, `changes_2026-04-30-changelogs.md`, `changes_2026-05-04.md`
- Archived changelogs under `docs/archive/`
- Existing task plan: `dashboard_tasks_2026-05-04.md`
- Architecture docs: `docs/architecture/bundle_catalog.md`, `docs/architecture/contracts.md`, `docs/architecture/sequence_flow.md`, `docs/architecture/system_overview.md`
- Feature docs under `docs/features/`
- Source files under `src/`, with emphasis on preview, app packaging, dashboard registries, mock endpoints, frontend rendering, and template/catalog loading
- Template files under `src/templates/bundles/`
- Static dashboard output files under `dashboard_output_templates/`

## Verification Run

Commands run during review:

```bash
python scripts/validate_templates.py
```

Result:

```text
All 15 bundle(s) validated successfully.
```

```bash
PYTHONPATH=src:. python - <<'PY'
from pathlib import Path
from catalog.bundle_catalog import BundleCatalog
cat = BundleCatalog(Path("src/templates/bundle_registry.yaml"))
cat.validate(Path("src/templates/bundles"))
cat.validate_template_consistency(Path("src/templates/bundles"))
cat.validate_variants(Path("src/templates/bundles"), Path("dashboard_output_templates"))
print("catalog validation ok")
PY
```

Result:

```text
catalog validation ok
```

```bash
PYTHONPATH=src:. pytest tests/unit/api/test_request_schemas.py tests/unit/api/test_preview_router.py tests/integration/test_early_preview.py -q
```

Result:

```text
31 passed in 3.73s
```

```bash
PYTHONPATH=src:. python - <<'PY'
from pathlib import Path
from agents.preview_generator.bundle_template_loader import BundleTemplateLoader
from agents.preview_generator.dashboard.static_output_registry import StaticDashboardOutputRegistry
from catalog.bundle_catalog import BundleCatalog
cat = BundleCatalog(Path("src/templates/bundle_registry.yaml"))
loader = BundleTemplateLoader()
dash = StaticDashboardOutputRegistry(catalog=cat)
missing = []
for b in cat.list_all():
    if len(loader.variant_keys(b.bundle_key)) != 3:
        missing.append((b.bundle_key, "variants", loader.variant_keys(b.bundle_key)))
    for v in b.variants:
        if loader.load(b.bundle_key, v.key) is None:
            missing.append((b.bundle_key, v.key, "missing app variant"))
        if dash.get_widgets(b.bundle_key, v.key) is None:
            missing.append((b.bundle_key, v.key, "missing dashboard widgets"))
print("missing", missing)
PY
```

Result:

```text
missing []
```

## Current Working State

The production preview path is:

```text
src/api/routers/preview.py
  -> src/orchestrators/preview_flow.py
  -> src/agents/preview_generator/service.py
  -> src/agents/preview_generator/bundle_template_loader.py
  -> src/agents/preview_generator/dashboard/static_output_registry.py
```

This path runs the LangGraph preview generator, overlays operational stores from `app-0*.json`, injects static dashboard widgets from `dashboard_output_templates/`, rebuilds `dashboard_generation_output`, and returns `AppPayloadResponseSchema`.

Catalog-backed variant resolution is working for all 13 canonical bundles:

```text
hr_management -> app-01/app-02/app-03 -> hr_management / hr_management_recruiting / hr_management_onboarding
ticketing -> app-01/app-02/app-03 -> ticketing / ticketing_customer_support / ticketing_facilities
project_mgmt -> app-01/app-02/app-03 -> project_management / project_management_client_delivery / project_management_creative
finance -> app-01/app-02/app-03 -> finance / finance_enterprise / finance_real_estate
marketing -> app-01/app-02/app-03 -> marketing / marketing_content / marketing_events
sales -> app-01/app-02/app-03 -> sales / sales_brokerage / sales_wholesale
healthcare -> app-01/app-02/app-03 -> healthcare_hospital / healthcare_clinic / healthcare_pharma
legal_services -> app-01/app-02/app-03 -> legal_litigation_firm / legal_corporate_counsel / legal_compliance_office
construction -> app-01/app-02/app-03 -> construction_general_contractor / construction_infrastructure / construction_residential
real_estate -> app-01/app-02/app-03 -> real_estate_property_mgmt / real_estate_brokerage / real_estate_commercial
education -> app-01/app-02/app-03 -> education_k12 / education_university / education_edtech
all_microservices -> app-01/app-02/app-03 -> all_microservices_enterprise_saas / all_microservices_ecommerce / all_microservices_fintech
generic -> app-01/app-02/app-03 -> generic_small_business / generic_consulting / generic_nonprofit
```

## Highest Priority Work

### 1. Make mock/demo previews use the same path as production previews

Files to update:

- `src/agents/app_generator/mock_builder.py`
- `src/api/deps.py`
- `src/api/routers/mock.py`
- `tests/unit/api/test_mock_router.py`
- Possible new integration test under `tests/integration/`

Problem:

`MockPayloadBuilder` currently calls `PreviewGeneratorService.generate()` directly. That means `/mock/{bundle_key}` returns raw pipeline output only. It does not run `PreviewFlow._apply_bundle_template()` and does not run `PreviewFlow._enrich_dashboard_widgets()`.

Why this matters:

The proposed frontend bundle selector/demo mode would use `/mock/{bundle_key}` to test dashboard rendering across bundles. If mock responses bypass `PreviewFlow`, the selector will not validate the actual `app-0*.json` overlays or static dashboard templates that were just integrated.

Recommended fix:

- Either inject `PreviewFlow` into `MockPayloadBuilder` and call `flow.run(...)` with a synthetic session id and minimal synthetic conversation history.
- Or keep `PreviewGeneratorService` but also inject `BundleTemplateLoader` and `StaticDashboardOutputRegistry`, then apply the same overlay/enrichment logic through shared helper functions.
- Prefer the first option if it can be done without circular dependencies, because it tests the real production path.

Acceptance criteria:

- `POST /mock/{canonical_bundle_key}` returns payloads with variant-overlaid stores from `src/templates/bundles/*/app-0*.json`.
- `POST /mock/{canonical_bundle_key}` returns `dummy_data_json.stores.dashboard_widgets` from `dashboard_output_templates/`.
- Mock tests assert that a variant-specific store appears for at least one bundle.
- Mock tests assert that `dashboard_generation_output.widgets.total` equals the number of injected widgets.

### 2. Add `preview_type` to `AppPayloadResponseSchema` specifically

Files to update:

- `src/api/schemas/app_payload.py`
- `src/api/routers/preview.py`
- `src/api/routers/app.py`
- `src/agents/preview_generator/edit/apply.py` if edit payloads should preserve the field
- `src/frontend/app.js`
- `src/api/schemas/response.py` only for reference; do not duplicate work there unless changing conversation response behavior
- `tests/unit/api/test_preview_router.py`
- `tests/integration/test_early_preview.py`

Problem:

`preview_type` already exists in `src/api/schemas/response.py` on `SessionStartedResponse` and `ConversationTurnResponse`. The gap is narrower: `src/api/schemas/app_payload.py::AppPayloadResponseSchema` does not include `preview_type`, so direct preview/app payload endpoints do not surface it even though the frontend reads `payload.preview_type` after `POST /sessions/{id}/preview`.

This is not a global missing-schema issue. It is specifically a mismatch between conversation-turn responses and app-payload responses.

Recommended fix:

- Add `preview_type: Literal["confirmed", "early"] | None = None` to `AppPayloadResponseSchema`.
- Pass `preview_type="confirmed"` from `POST /sessions/{id}/preview`.
- Pass `preview_type="early"` from `POST /sessions/{id}/preview/early`.
- Preserve `preview_type` through `POST /sessions/{id}/preview/edit` when the current preview includes it.
- Decide whether `POST /sessions/{id}/app` should return `preview_type="confirmed"` or leave it `None`; document the decision in tests.

Acceptance criteria:

- Early preview responses include `"preview_type": "early"`.
- Confirmed preview responses include `"preview_type": "confirmed"`.
- Frontend dashboard badge reliably shows `"Early Preview"` for early previews.

### 3. Pass `generation_json` when finalizing the app

Files to update:

- `src/frontend/api.js`
- `src/frontend/app.js`
- `tests/unit/api/test_request_schemas.py` if frontend contract examples are mirrored in tests
- Optional frontend/manual test notes

Problem:

`GenerateAppRequest` already supports optional `generation_json`, and `src/api/routers/app.py` passes it to `AppGeneratorService.assemble()`. But `src/frontend/app.js` still calls:

```javascript
generateApp(state.sessionId, state.previewPayload.dummy_data_json)
```

This omits the personalized preview `generation_json`, which can force the final app path back toward static `app.json` behavior.

Recommended fix:

```javascript
export async function generateApp(sessionId, dummyDataJson, generationJson = null) {
  return requestJson(`/sessions/${sessionId}/app`, {
    method: 'POST',
    body: JSON.stringify({
      dummy_data_json: dummyDataJson,
      ...(generationJson ? { generation_json: generationJson } : {}),
    }),
  });
}
```

Then call it with:

```javascript
const finalPayload = await generateApp(
  state.sessionId,
  state.previewPayload.dummy_data_json,
  state.previewPayload.generation_json,
);
```

Acceptance criteria:

- The final app payload uses the same `generation_json` that the user previewed.
- Existing static fallback still works when `generation_json` is omitted.

### 4. Audit preview-vs-app contract drift end-to-end

Files to update:

- `src/api/routers/preview.py`
- `src/api/routers/app.py`
- `src/agents/app_generator/service.py`
- `src/agents/app_generator/validators.py`
- `src/domain/models/app_payload.py`
- `src/api/schemas/app_payload.py`
- `src/frontend/app.js`
- `tests/unit/app_generator/test_service.py`
- `tests/integration/test_preview_generation_static_outputs.py`
- `tests/integration/test_preview_edit_flow.py`
- A new integration test that generates a preview, finalizes the app, and compares the two payloads

Problem:

Preview and app are separate stages with overlapping payloads. Preview is the draft the user sees; app is the finalized package. Because the codebase historically had an older static app-generation path, there is risk that the final app payload does not match the preview payload.

Specific drift risks to check:

- Preview uses `PreviewFlow` with `app-0*.json` overlays, but app finalization may fall back to static `app.json`.
- Preview returns enriched `dashboard_widgets` and `dashboard_generation_output`, but app finalization may lose, rebuild, or reshape them.
- Preview uses canonical `bundle_key`, but app validation still has legacy render-key compatibility paths.
- Preview can include `generation_json.preview_warnings`, while app finalization may drop that metadata or treat it as invalid.
- Preview edits mutate a client payload, but final app packaging may not preserve those edited changes unless the edited `generation_json` and `dummy_data_json` are submitted.
- Early preview payloads may be visually useful but should not be treated the same as confirmed/final app payloads without a clear product decision.

Recommended fix:

- Add a single end-to-end test that follows the real user path: conversation/session setup -> preview generation -> optional preview edit -> final app generation.
- Assert that final app output preserves the preview's `bundle_key`, `generation_json`, `dummy_data_json.stores`, dashboard widgets, and key config fields unless a deliberate transformation is documented.
- Add a small helper or explicit comments naming the boundary: preview produces the draft payload; app packages the accepted preview payload.
- Confirm frontend sends both `generation_json` and `dummy_data_json` from the current preview state, not stale copies.

Acceptance criteria:

- A test fails if final app generation silently reloads static `app.json` when preview `generation_json` is available.
- A test fails if final app generation drops dashboard widgets from a confirmed preview.
- A test fails if edited preview payloads are not preserved during finalization.
- Early preview finalization behavior is explicitly blocked, allowed with warning, or documented as out of scope.

### 5. Fix broken frontend preview state branch

Files to update:

- `src/frontend/app.js`
- `src/frontend/styles.css` if new states are intentionally introduced
- Frontend/manual test notes

Problem:

After preview generation, `handleGeneratePreview()` sets:

```javascript
state.lastStatus = 'preview_ready';
```

But `applyTurnResponse()` checks:

```javascript
state.lastStatus === 'ready_for_preview'
```

This is a functional bug, not only a naming inconsistency. Once preview generation sets `preview_ready`, any later branch that expects `ready_for_preview` will not run. In the current file this affects the action-button branch in `applyTurnResponse()` and can cause UI state to drift from backend state.

Recommended fix:

- Prefer backend vocabulary and set `state.lastStatus = 'ready_for_preview'`.
- If a frontend-only `preview_ready` state is required, define it deliberately and update every branch/CSS selector that depends on preview readiness.
- Add a regression test or manual QA step that confirms the preview-ready action branch still runs after preview generation and after subsequent turn responses.

Acceptance criteria:

- Preview generation does not leave `state.lastStatus` in a value that later preview-ready branches ignore.
- Pipeline status badge remains styled and semantically aligned after preview generation.
- The UI can still present the correct next action after preview generation.

### 6. Wire the frontend early preview flow

Files to update:

- `src/frontend/api.js`
- `src/frontend/app.js`
- `src/frontend/components.js` if adding a reusable action button renderer
- `src/frontend/styles.css`

Problem:

`generateEarlyPreview()` exists in `src/frontend/api.js`, but it is not imported or called by `src/frontend/app.js`. There is no UI affordance for `/sessions/{id}/preview/early`.

Recommended fix:

- Import `generateEarlyPreview` in `app.js`.
- Add a `handleGenerateEarlyPreview()` handler.
- Show an "Early Preview" action when status is `awaiting_input` and a `sessionId` exists.
- Set `state.previewType = payload.preview_type || "early"` after success.
- Consider hiding or disabling the deploy button when `previewType === "early"` until the user confirms a bundle.

Acceptance criteria:

- A user can request an early preview before bundle confirmation.
- The frontend shows warning text from the backend.
- The dashboard badge shows `"Early Preview"`.
- Early preview does not encourage final deployment unless that is an intentional product decision.

## Frontend Dashboard Work

### 7. Add a bundle selector/demo mode that exercises real preview-shaped payloads

Files to update:

- `src/frontend/api.js`
- `src/frontend/app.js`
- `src/frontend/index.html`
- `src/frontend/styles.css`
- Possibly `src/api/routers/bundles.py` if the frontend should fetch canonical keys dynamically

Problem:

Developers still need a fast way to render each bundle without completing a full AI conversation.

Recommended fix:

- Add a dropdown or compact demo rail listing canonical bundle keys from `/bundles` or a static list.
- On selection, call `POST /mock/{bundle_key}` with `{}` as the body.
- Load the response into `state.previewPayload`.
- Set `state.previewType = "confirmed"` or `"mock"` depending on whether the schema is extended beyond confirmed/early.

Important dependency:

Do task 1 first. Otherwise the bundle selector will test raw pipeline output rather than the integrated `PreviewFlow` output.

Acceptance criteria:

- At least `hr_management`, `ticketing`, `finance`, `construction`, and `generic` can be selected and rendered without a conversation.
- The selector uses canonical bundle keys, not render keys like `hr_hub` or folder names like `project_ops`.
- Ambiguous render keys like `project_mgmt` and `ticketing` are not silently used as aliases where they conflict with canonical identity.

### 8. Remove duplicate empty preview states

Files to update:

- `src/frontend/index.html`
- `src/frontend/components.js`
- `src/frontend/app.js`

Problem:

`index.html` contains a static `.preview-placeholder`, while `renderDashboard(null, ...)` returns `.dashboard-empty`. The app eventually replaces the static markup, but the first-load model is split.

Recommended fix:

- Remove the static `.preview-placeholder` from `index.html`.
- Call `refreshUI()` once during initialization after the first system message.
- Let `renderDashboard()` own the empty state.

Acceptance criteria:

- There is one empty preview state.
- First load, post-session-start, and post-reset states all render the same placeholder.

### 9. Add responsive dashboard breakpoints

Files to update:

- `src/frontend/styles.css`

Problem:

The executive dashboard grid mostly responds through CSS grid, but there is no explicit breakpoint for narrow preview panels.

Recommended fix:

```css
@media (max-width: 900px) {
  .app-container {
    flex-direction: column;
  }

  .sidebar {
    width: 100%;
    max-height: 48vh;
  }

  .exec-grid-2col {
    grid-template-columns: 1fr;
  }

  .exec-header {
    flex-direction: column;
  }

  .exec-summary-bar {
    justify-content: flex-start;
  }
}
```

Acceptance criteria:

- Dashboard remains usable on tablet-width and phone-width screens.
- The sidebar does not permanently squeeze the preview panel below usable width.

### 10. Harden generic table rendering

Files to update:

- `src/frontend/components.js`

Problems:

- Nested objects and arrays can render as `[object Object]`.
- Currency formatting condition has operator-precedence risk:

```javascript
if (typeof val === 'number' && String(h).includes('amount') || String(h).includes('value') || String(h).includes('revenue')) {
```

Recommended fix:

- Parenthesize the field-name checks.
- Only currency-format numeric values.
- Serialize object/array cells safely with a compact formatter.
- Consider capping long strings.

Suggested helper:

```javascript
function formatCellValue(value) {
  if (value === null || value === undefined) return '';
  if (Array.isArray(value)) return value.map(v => String(v)).join(', ');
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}
```

Acceptance criteria:

- No table cell renders `[object Object]`.
- No non-numeric field renders as `$NaN`.

### 11. Escape all frontend error-message paths

Files to update:

- `src/frontend/app.js`

Problem:

`appendErrorMessage()` interpolates `error.message` directly into HTML. The risk is broader than the helper alone because multiple catch paths pass raw error messages into it:

- `handleSendMessage()` catch path around current `src/frontend/app.js:124`
- `handleConfirmBundle()` catch path around current `src/frontend/app.js:147`
- `handleGeneratePreview()` catch path around current `src/frontend/app.js:173`
- `handleDeployApp()` catch path around current `src/frontend/app.js:197`

Any server-controlled error detail that reaches those paths can become HTML unless escaped before insertion.

Recommended fix:

- Import or expose `escapeHtml`, or route error rendering through `renderMessage("system", ...)`.
- Make `appendErrorMessage()` the safe boundary by escaping internally, so all current and future callers are protected.
- Add a regression check using an error message such as `<img src=x onerror=alert(1)>` and verify it renders as text.

Acceptance criteria:

- Server error detail text cannot inject HTML into the chat log.

## Backend Contract and Validation Work

### 12. Decide whether dashboard output templates should carry external dashboard IDs

Files to inspect/update:

- `dashboard_output_templates/*.json`
- `dashboard_template_static_ids.json`
- `src/agents/preview_generator/dashboard/static_output_registry.py`
- `tests/unit/dashboard/test_static_output_registry.py`
- `changes_2026-04-30-2.md` if correcting documentation/changelog notes is allowed

Problem:

The changelog says redundant local `"id": "widget-X"` fields were removed and that the system relies on `external_id`, but the current dashboard output templates still contain local `"id": "widget-X"` fields and do not contain `external_id` fields. The authoritative ID file also exists as root `dashboard_template_static_ids.json`, not as `dashboard_output_templates/0_dashboard_template_static_ids.json`.

Why this matters:

If frontend rendering only needs internal widget layout, current files are fine. If Murad/CJ dashboard integration expects external template IDs, the static outputs need a clearer schema and validation.

Recommended fix:

- Decide the intended widget identity contract.
- If external IDs are required, add them to every static widget or add a resolver that joins `dashboard_template_static_ids.json` by dashboard/widget name.
- If external IDs are not required, update the changelog/task docs to avoid sending future reviewers on a ghost hunt.

Acceptance criteria:

- Static dashboard output schema is explicitly documented.
- Unit tests validate the chosen ID contract.
- No mismatch between docs/changelogs and current files.

### 13. Add stronger template/dashboard cross-validation

Files to update:

- `scripts/validate_templates.py`
- `catalog/bundle_catalog.py`
- `tests/integration/test_bundle_catalog.py`
- `tests/unit/dashboard/test_static_output_registry.py`

Current validation checks:

- Bundle catalog loads.
- Template consistency passes.
- Variants point to existing `app-0*.json` and dashboard files.
- Dashboard output files have non-empty `widgets` arrays.

Missing validation:

- Dashboard widget titles or data source expectations are not checked against stores in the matching `app-0*.json`.
- Widget IDs are not checked for uniqueness per file.
- Position objects are not validated for required keys.
- Dashboard output schema does not detect stale local ID versus external ID expectations.

Recommended fix:

- Validate each dashboard output widget has `type`, `title`, and `position`.
- Validate `position` includes `row`, `col`, `width`, and `height`.
- Validate widget IDs are unique inside each dashboard file if local IDs remain.
- Optionally validate that number widgets correspond to KPI labels/keys in the matching app variant when a naming convention exists.

Acceptance criteria:

- `python scripts/validate_templates.py` fails for malformed dashboard widgets.
- Tests cover at least one malformed dashboard output.

### 14. Decide whether finance and sales should emit generic `projects`

Files to update:

- `src/agents/preview_generator/nodes/emit.py`
- `tests/integration/test_preview_generator_flow.py`
- `src/frontend/components.js` depending on rendering decision

Problem:

`changes_2026-05-04.md` notes that `finance` and `sales` can still carry generic `stores.projects` noise from pipeline output. This is currently tolerated, but it can produce irrelevant frontend sections.

Recommended fix:

- If frontend should not render generic projects for finance/sales, set `secondary=None` for those bundles in `_STORE_SCHEMA`.
- If those projects are intentionally useful, rename or shape them to be domain-specific and document it.

Acceptance criteria:

- Finance preview does not show irrelevant generic project data unless intentionally designed.
- Sales preview does not show irrelevant generic project data unless intentionally designed.

### 15. Return deep copies from `BundleTemplateLoader`

Files to update:

- `src/agents/preview_generator/bundle_template_loader.py`
- `tests/unit/domain/test_bundle_registry_validation.py` or a new loader test

Problem:

`BundleTemplateLoader.load()` returns a direct reference to the cached dict. `PreviewFlow` currently does not mutate it, so this is not a live bug. But it is inconsistent with `StaticDashboardOutputRegistry`, which returns deep copies because callers may mutate.

Recommended fix:

- Return `copy.deepcopy(chosen)` from `load()`.
- Update tests to assert cache isolation.

Acceptance criteria:

- Mutating a loaded template in a caller cannot mutate the cache for later requests.

## Documentation Work

### 16. Update stale docs that still refer to old dashboard/template paths

Files to update:

- `docs/features/preview_generator.md`
- `docs/features/ai_interpreter.md`
- `README.md`
- `PLAN.md`
- Potentially old changelog follow-up notes, if desired

Observed stale areas:

- Some docs still discuss earlier `dashboard_templates/` flows.
- Some examples still use legacy render keys like `hr_hub` or folder names like `project_ops` where canonical API keys should be shown.
- `docs/features/ai_interpreter.md` still references older `ExtractedInfo` / `SuggestedBundles` terminology in places where current code uses `ExtractionResult` and `ClassificationResult`.

Recommended fix:

- Make public/API examples canonical: `hr_management`, `project_mgmt`, `ticketing`, etc.
- Keep render keys documented as internal compatibility metadata.
- Document current preview path as `PreviewFlow` plus static app/dashboard overlays.

Acceptance criteria:

- A new developer can identify canonical bundle keys without reading changelogs.
- Docs match the current `src` architecture and response schemas.

### 17. Replace or supersede `dashboard_tasks_2026-05-04.md`

Files to update:

- `dashboard_tasks_2026-05-04.md`
- This file, if used as the new source of truth

Problem:

The May 4 task file is still useful, but it misses the mock endpoint path problem and now has some tasks that should be re-prioritized behind that.

Recommended fix:

- Treat this May 5 review as the current to-do source.
- Either archive the May 4 file or add a note at the top pointing to `todo_review_2026-05-05.md`.

Acceptance criteria:

- There is one obvious current dashboard integration task list.

## Suggested Implementation Order

1. Update mock/demo backend path so `/mock/{bundle_key}` exercises `PreviewFlow`.
2. Fix the broken frontend `preview_ready` vs `ready_for_preview` branch.
3. Escape all frontend error-message paths.
4. Add `preview_type` to `AppPayloadResponseSchema` and preview route responses.
5. Pass `generation_json` from frontend finalization.
6. Add end-to-end preview-vs-app contract drift tests.
7. Wire the early preview frontend button.
8. Add bundle selector/demo UI.
9. Fix empty state and responsive CSS.
10. Harden generic dashboard table rendering.
11. Decide and validate dashboard widget identity contract.
12. Decide whether finance/sales should emit `projects`.
13. Update docs and retire stale task notes.

## Residual Risks

- The production preview path appears structurally sound, but full cross-bundle browser QA has not been run.
- Existing frontend rendering is adaptive, but it does not yet prove every domain-specific store renders well.
- Static dashboard widgets are injected into payloads but the frontend currently filters `dashboard_widgets` and `dashboard_generation_output` out of generic table rendering, so visual validation is mostly based on stores/KPIs rather than widget layouts.
- The mock endpoint is the main trap: using it for QA before task 1 is fixed could produce false confidence.
- Full repo preflight was not run during this review.

## Local Test Plan After Fixes

Run backend checks:

```bash
python scripts/validate_templates.py
PYTHONPATH=src:. pytest tests/unit/dashboard tests/unit/api/test_mock_router.py tests/unit/api/test_preview_router.py -q
PYTHONPATH=src:. pytest tests/integration/test_preview_generator_flow.py tests/integration/test_preview_generation_static_outputs.py tests/integration/test_early_preview.py -q
```

Run frontend/manual checks:

```bash
make dev
```

Manual browser checks:

- Start a normal conversation, confirm a bundle, generate preview, finalize app.
- Start a conversation and trigger early preview before confirmation.
- Use demo selector for at least `hr_management`, `ticketing`, `finance`, `construction`, and `generic`.
- Confirm the dashboard never shows `[object Object]`, `$NaN`, raw `dashboard_widgets`, or raw `dashboard_generation_output`.
- Confirm early preview warnings and badge labels appear.
- Confirm mobile/narrow viewport layout remains usable.
