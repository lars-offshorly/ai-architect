# Dashboard FE — Remaining Tasks

**Branch:** `RENDER-PREVIEW/dev`  
**Date:** 2026-05-04  
**Context:** The new generalized `renderDashboard` in `src/frontend/components.js` is implemented. This doc lists what still needs to happen before the dashboard is fully functional end-to-end.

---

## 1. Add a bundle selector / demo mode to the frontend

**Why:** Right now there is no way to render the new dashboard without running a full AI conversation to completion. Developers and reviewers need to test the dashboard against each bundle type directly.

**What to do:**

Add a `POST /mock/{bundle_key}` caller to `api.js` and a simple bundle picker UI to `index.html` + `app.js` that:

1. Displays a dropdown of all canonical bundle keys (ticketing, hr_hub, construction, finance, sales, project_ops, marketing, etc.).
2. On selection, calls `POST /mock/{bundle_key}` (requires `ENABLE_MOCK_ENDPOINTS=true` in `.env`).
3. Feeds the response directly into `state.previewPayload` and calls `refreshUI()`.

The mock endpoint response shape differs slightly from the preview endpoint — `display_name` is at the top level and `dummy_data_json` contains `stores`. `renderDashboard` already handles this shape via `getStores()` but confirm `display_name` is passed through correctly.

---

## 2. Fix `AppPayloadResponseSchema` — missing `preview_type` field

**Why:** `app.js` reads `payload.preview_type` in `handleGeneratePreview` to set the badge label (`'Early Preview'` vs `'Preview Mode'`). But `AppPayloadResponseSchema` in `src/api/schemas/app_payload.py` does **not** include a `preview_type` field — it's only on `ConversationTurnResponse` and `SessionStartedResponse`.

**Effect:** `state.previewType` is always `null`; the badge always reads `"Preview Mode"` even for early previews.

**Fix options (pick one):**
- Add `preview_type: Literal["confirmed", "early"] | None = None` to `AppPayloadResponseSchema`, and populate it in the two `_execute_preview_pipeline` call sites in `preview.py` (pass `"confirmed"` for the normal path, `"early"` for the early path).
- Or: keep it out of the schema and handle the badge label in the frontend by tracking which API path was called (`/preview` vs `/preview/early`).

---

## 3. Wire up `generateEarlyPreview` in `app.js`

**Why:** `api.js` already exports `generateEarlyPreview` (calls `POST /sessions/{id}/preview/early`) but `app.js` never calls it. There is no UI affordance to trigger an early preview.

**What to do:**

- Add an "Early Preview" button that appears when the session is `awaiting_input` (i.e. the conversation hasn't reached `pending_confirmation` yet).
- Hook it to a new `handleGenerateEarlyPreview()` handler that mirrors `handleGeneratePreview` but calls `generateEarlyPreview(state.sessionId)`.
- Set `state.previewType = 'early'` on success so the badge renders correctly (pending task 2 above).

---

## 4. Confirm `generateApp` request body is complete

**Why:** `app.js` line 186 calls `generateApp(state.sessionId, state.previewPayload.dummy_data_json)`. The `api.js` function sends `{ dummy_data_json }` but `GenerateAppRequest` also accepts an optional `generation_json`. The preview payload includes a `generation_json` field — omitting it forces the backend to fall back to the static `app.json` template, which may not match the personalized preview the user just saw.

**Fix:**
```js
// app.js — handleDeployApp
const finalPayload = await generateApp(
  state.sessionId,
  state.previewPayload.dummy_data_json,
  state.previewPayload.generation_json,   // add this
);
```
And update `api.js`:
```js
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

---

## 5. Responsive layout for the preview panel

**Why:** The dashboard uses `.exec-grid-2col` (two equal columns) for chart pairs. At the current fixed 420px sidebar + flexible main layout, the right panel can be narrow on smaller screens. The two-column chart grid collapses gracefully at CSS grid minimums but there is no explicit `@media` breakpoint.

**What to do:**

Add to `styles.css`:
```css
@media (max-width: 900px) {
  .exec-grid-2col { grid-template-columns: 1fr; }
  .exec-header { flex-direction: column; }
  .exec-summary-bar { justify-content: flex-start; }
}
```

---

## 6. Verify `stores` shape for bundles that use `app-01.json` vs pipeline-generated data

**Why:** The new normalizers read from `payload.dummy_data_json.stores` (live pipeline output) as well as `payload.stores` (direct bundle template shape). The mock endpoint wraps pipeline output in `dummy_data_json: { bundle_key, stores: {...} }`, which `getStores()` handles. But the early preview path may return a different nesting depending on how `PreviewFlow.run()` assembles its output.

**What to do:**

Manually test at least three bundles via the mock endpoint (suggested: `ticketing`, `hr_hub`, `finance`) and verify the rendered sections match expected stores. Check the browser console for any `[object Object]` values in table cells (indicates a nested object that the generic renderer doesn't flatten).

---

## 7. Empty-state handling for the `dashboard-empty` fallback

**Why:** `index.html` includes an inline placeholder `<div class="preview-placeholder">` that is overwritten by `refreshUI()` when `state.previewPayload` is null. The new `renderDashboard` returns a `.dashboard-empty` div when payload is absent, but `index.html` still has the old placeholder markup — there are now two empty states competing on first load (the static HTML one and the one rendered by `refreshUI` on `startSession`).

**Fix:**

Either:
- Remove the static placeholder from `index.html` (let `renderDashboard`'s empty state handle it entirely), or
- Move the placeholder into a `renderEmptyPreview()` function in `components.js` and call it explicitly from `app.js` on init instead of relying on the HTML default.

The simpler option is to remove the `<div class="preview-placeholder">` block from `index.html`.

---

## Priority order

| # | Task | Effort | Blocks |
|---|------|--------|--------|
| 1 | Bundle selector / demo mode | Medium | Manual testing of all bundles |
| 7 | Remove duplicate empty state in index.html | Trivial | Clean first-load render |
| 5 | Responsive breakpoints | Trivial | Narrow viewport support |
| 4 | Pass `generation_json` to `generateApp` | Small | Correct final deploy payload |
| 2 | Add `preview_type` to `AppPayloadResponseSchema` | Small | Accurate badge label |
| 3 | Wire up early preview button | Small | Full early-preview flow |
| 6 | Cross-bundle render verification | QA | Confidence before merge |
