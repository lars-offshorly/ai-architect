# Phase 8 Cleanup Plan

**Draft author:** Laira  
**For execution by:** CJ  
**Source:** [PARALLEL_WORK_SPLIT.md](../PARALLEL_WORK_SPLIT.md) — Phase 8 tasks

---

## Purpose

This document is a pre-execution checklist for Phase 8 legacy cleanup. It lists every file targeted for deletion or demotion, the pre-condition that must be true before CJ acts on it, and the current dependency status as of the audit date (2026-05-21).

Laira does not execute these deletions. She flags this plan to CJ for review; CJ runs each step when its pre-condition is met.

---

## Execution Rules

1. **Check the pre-condition first.** Do not delete a file before its stated condition is true.
2. **Run all tests after each deletion.** All Phase 6 integration tests must stay green.
3. **8.3 is the safest first step** — `src/generator/` is a confirmed orphan (see audit below).
4. **8.6 / 8.7 are highest risk** — `template_repository.py` and `template_selection.py` have wide blast radius; remove only the dummy_data paths, not the whole files.
5. **8.2 is a demotion, not a deletion** — `bundle_template_loader.py` must keep its dashboard-enrichment surface.

---

## File Inventory

### 8.1 — Delete `src/agents/preview_generator/nodes/sample_data.py`

| Field | Detail |
|---|---|
| **Action** | Delete file + remove node registration from `pipeline.py` + update `tests/unit/preview_generator/test_sample_data_population.py` |
| **Pre-condition** | v2 pipeline is live end-to-end (`emit_v2` node active; `skip sample_data` toggle confirmed working) |
| **Current status** | Active — imported and registered in `src/agents/preview_generator/pipeline.py` |
| **Why** | v2 generates workspace data via the tenant provisioning manifest; the sample data node is a v1-only concern |
| **Tests to update** | `tests/unit/preview_generator/test_sample_data_population.py` — CJ updates or deletes alongside the source file |

---

### 8.2 — Demote `src/agents/preview_generator/bundle_template_loader.py`

| Field | Detail |
|---|---|
| **Action** | Remove the v1 store-overlay surface; keep only the dashboard-enrichment surface |
| **Pre-condition** | v2 template system is ready and `_apply_bundle_template()` in `PreviewFlow` no longer uses the overlay path |
| **Current status** | Active — used by `src/orchestrators/preview_flow.py` in `_apply_bundle_template()` for v1 store overlays; also used for dashboard widget injection |
| **Why** | v2 no longer relies on bundle variant JSON overlays for data stores; dashboard enrichment is orthogonal and must be preserved |
| **Note** | This is a **demotion**, not a full deletion. The dashboard enrichment path (`PIPELINE_OWNED_STORE_KEYS` and widget loading) stays. |

---

### 8.3 — Delete `src/generator/` (entire directory)

| Field | Detail |
|---|---|
| **Action** | Delete entire directory after CJ sign-off |
| **Pre-condition** | CJ reviews this audit and confirms sign-off |
| **Current status** | **ORPHAN — confirmed safe to delete** (see audit below) |
| **Why** | Legacy generator package fully superseded by the v2 pipeline; no production code depends on it |
| **Tests to delete** | `tests/integration/test_generator_validator.py` and `tests/integration/test_generator_personaliser.py` — these are the only consumers and go with the source |

#### 8.3 Generator Orphan Audit

**Audit date:** 2026-05-21  
**Auditor:** Laira

**Files in `src/generator/`:**

| File | Contents |
|---|---|
| `__init__.py` | Empty compatibility shim — "Legacy generator compatibility package." |
| `schemas.py` | Legacy Pydantic models: `ModuleConfig`, `WorkspaceMeta`, `GenerationJSON`, `StoreData`, `DummyDataJSON`, `TemplateMetadata`, `RetrievedTemplate` |
| `personaliser.py` | Async LLM-based template personalisation (`personalise_template()`) |
| `validator.py` | Output validation for legacy generator — validates `GenerationJSON` + `DummyDataJSON` together |

Note: `__pycache__/retriever.cpython-310.pyc` exists with no corresponding `retriever.py`, indicating that file was already deleted previously.

**Import scan results:**

```
Production code (src/):   ZERO imports from generator.*
Test code (tests/):       2 files
  tests/integration/test_generator_personaliser.py
  tests/integration/test_generator_validator.py
Entrypoints:              ZERO (src/main.py, src/api/app.py — no reference)
```

Verified with:
```bash
grep -rn "from generator\|import generator" src/ --include="*.py"   # → NONE
grep -rn "from generator\|import generator" tests/ --include="*.py" # → 2 files above
grep -n "generator" src/main.py src/api/app.py                      # → NONE
```

**Verdict: ABSOLUTE ORPHAN.** Zero production dependencies. The two test files exist only to test the orphan itself — they go with it.

---

### 8.4 — Delete `src/agents/app_generator/config_assembly/`

| Field | Detail |
|---|---|
| **Action** | Delete entire directory (keep `relationship_mapper.py` only if v2 transition still requires it — CJ decides) |
| **Pre-condition** | v2 `AppPayload` assembly no longer calls `map_relationships()`; CJ confirms |
| **Current status** | Active — `src/agents/app_generator/service.py` calls `map_relationships()` from `config_assembly/` in its `assemble()` method |
| **Why** | v2 manifest encodes entity relationships via catalog references, not the config_assembly mapper |

---

### 8.5 — Remove `v2_manifest` field wrapper from `src/api/schemas/app_payload.py`

| Field | Detail |
|---|---|
| **Action** | Once `v2_manifest` is the *only* field returned, remove the explicit field wrapper from `AppPayloadResponseSchema` |
| **Pre-condition** | BE confirms full migration — v1 fields (`generation_json`, `dummy_data_json`) are no longer consumed anywhere downstream |
| **Current status** | Active — `v2_manifest` is an optional side-load field; v1 fields still present and returned by `/preview` |
| **Why** | Schema cleanup after v2-only state is confirmed; the wrapper itself becomes redundant once v2 is the sole contract |

---

### 8.6 — Remove `dummy_data.json` load paths from `src/repositories/template_repository.py` and `src/domain/services/template_selection.py`

| Field | Detail |
|---|---|
| **Action** | Remove only the `dummy_data.json` disk-load paths from both files — do **not** delete the files themselves |
| **Pre-condition** | v2 replaces all dummy data loading; no active code path calls `get_dummy_data()` or equivalent |
| **Current status** | Active and broad — both files support all template types (`preview.json`, `app.json`, `dummy_data.json`); removal is surgical, not whole-file |
| **Why** | v2 manifest replaces the need to load pre-baked `dummy_data.json` files from disk |
| **Risk** | High — these files have wide blast radius. Grep all callers before removing any path. |

---

### 8.7 — Delete deprecated validators and contract checks

**Two files targeted:**

#### `src/agents/app_generator/validators.py`

| Field | Detail |
|---|---|
| **Action** | Delete `validate_generation_json()` and `validate_dummy_data_json()` functions (or the whole file if nothing else remains) |
| **Pre-condition** | `generation_json` / `dummy_data_json` fully deprecated in the app generator path |
| **Current status** | Active — called by `src/agents/app_generator/service.py` (both validators) and `src/agents/app_generator/mock_builder.py` (`validate_dummy_data_json`) |

#### `src/agents/app_generator/contract.py`

| Field | Detail |
|---|---|
| **Action** | Delete file |
| **Pre-condition** | Same as validators — v1 contract fully deprecated |
| **Current status** | Active — `AppPayloadContract` is imported by `src/agents/app_generator/service.py` |

---

### 8.8 — Delete `src/api/adapters/v2_manifest_adapter.py`

| Field | Detail |
|---|---|
| **Action** | Delete file + prune its imports from `src/api/routers/preview.py` and `src/api/deps.py` |
| **Pre-condition** | The v2 orchestrator path always provides `v2_manifest`; the adapter fallback is never reached |
| **Current status** | Active — `src/api/routers/preview.py` calls `build_v2_manifest()` from this adapter as a fallback when the orchestrator does not supply a manifest |
| **Why** | Once the orchestrator (Task 3.2) always produces `payload.v2_manifest`, the adapter is dead code |

---

## Dependency Summary

| Task | File(s) | Safe now? | Blocker |
|---|---|---|---|
| 8.3 | `src/generator/` | **Yes** | CJ sign-off only |
| 8.1 | `nodes/sample_data.py` | No | v2 pipeline must be live |
| 8.8 | `v2_manifest_adapter.py` | No | Task 3.2 (orchestrator wire-up) |
| 8.4 | `config_assembly/` | No | Task 4.4 (AppGenerator v2 assembly) |
| 8.2 | `bundle_template_loader.py` | No | v2 template system ready |
| 8.5 | `app_payload.py` v2 field | No | BE confirms full migration (Task 7.1) |
| 8.6 | `template_repository.py` paths | No | All dummy_data callers gone |
| 8.7 | `validators.py`, `contract.py` | No | v1 generation path fully removed |

---

## Verification Checklist

After each Phase 8 step, CJ runs:

```bash
pytest tests/unit/ tests/integration/ -x -q
```

All tests must pass with **no skips** before the next deletion proceeds.
