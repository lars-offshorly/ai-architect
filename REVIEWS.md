# Code Review

**Commit:** `3fb75a1b6fc66821ab4894c194271a51577d8903`  
**Reviewer:** Senior Python Developer (Antigravity Assistant)  
**Date:** March 31, 2026

## Summary
Great work on implementing the early preview support and the preselection path. The refactoring of `ConversationFlow` into structured request/context objects is a significant improvement for maintainability. Bypassing the classifier for preselected bundles is a smart optimization for both latency and LLM costs.

Below are some specific comments and suggestions for minor improvements.

---

## Detailed Review

### 1. `src/agents/interpreter/classifier.py`

| Lines | Comment |
| :--- | :--- |
| 32-45 | **[Optimization]** The `_apply_intent_boost` function performs a linear search inside a loop (`any(intent in ti.lower() for ti in bundle.typical_intents)`). While the list of intents is likely small, ensuring `intent.lower()` is calculated once outside the loop is good practice. Also, consider if `typical_intents` should be pre-processed to lowercase in the bundle model itself to avoid repeated `.lower()` calls. |
| 84 | **[Performance]** `bundles = self._catalog.list_all()` is called inside `classify`. If the catalog is large, this could be expensive. Consider if this list can be cached or passed in if already available in the caller context. |

### 2. `src/domain/models/session.py`

| Lines | Comment |
| :--- | :--- |
| 259-265 | **[Consistency]** Adding `preselected_intent` and `preselected_bundle_key` to the session model is correct. It ensures that the "intent" of the session is preserved across turns without relying solely on extraction. |

### 3. `src/orchestrators/conversation_flow.py`

| Lines | Comment |
| :--- | :--- |
| 294-301 | **[Maintainability]** `_PREVIEW_KEYWORDS` are hardcoded here. As this list grows or requires localization, it might be better to move these to a configuration file or a dedicated `constants.py` module. |
| 470-499 | **[Design]** The `_coerce_turn_request` method is a good bridge for backward compatibility. However, once the transition to `ConversationTurnRequest` is complete, I'd recommend removing this "dual-mode" support to keep the API clean and purely type-hinted. |
| 601-607 | **[Logic]** The fallback to `_FORCE_PREVIEW_FALLBACK_BUNDLE` ("all_microservices") is a sensible default for an "early preview" request when no classification has happened yet. |

### 4. `tests/integration/test_early_preview.py`

| Lines | Comment |
| :--- | :--- |
| 851 | **[Nit]** Minor typo in class name: `TestForcePreviawViaReply` should be `TestForcePreviewViaReply`. |

---

## Conclusion
The implementation is solid and follows the project's architectural patterns. The added tests are comprehensive and cover the new edge cases introduced by the early preview logic. Once the minor nitpicks are addressed, this is a very strong contribution.

**Status:** LGTM (with minor suggestions)

---

**Commit:** `684d35d61d2ce2772fd1f2e9bc1f9a55bc6a85e0`  
**Reviewer:** Senior Python Developer (Antigravity Assistant)  
**Date:** March 31, 2026

## Summary
This commit introduces a more robust and scalable approach to information extraction and state management. The transition from hardcoded rules to a catalog-driven signal detection system is a major win for the architecture. The addition of signal accumulation ensures that the assistant "remembers" discovered facts across a multi-turn conversation.

## Detailed Review

### 1. `src/agents/interpreter/extractor.py`

| Lines | Comment |
| :--- | :--- |
| 65-81 | **[Architectural Win]** Moving synonym and phrase matching into a pre-computed index in the `Extractor` is a great move. It makes the signal detection much more consistent across the system. |
| 92-112 | **[Performance]** `_normalize_keywords` performs a nested loop for phrase matching. For a large catalog, this $O(N \times M)$ operation could slow down extraction. Consider using a more efficient string matching algorithm (like Aho-Corasick) if the synonym list grows to thousands of entries. |

### 2. `src/agents/interpreter/missing_fields.py`

| Lines | Comment |
| :--- | :--- |
| 341-380 | **[Accuracy]** The signal overlap detection logic is very thorough, combining tokenization with substring matching. This should significantly reduce false negatives in missing field detection. |

### 3. `src/agents/interpreter/rules.py`

| Lines | Comment |
| :--- | :--- |
| 437-548 | **[Clean Code]** Removing the massive hardcoded `_SIGNAL_MAP` and `_SIGNAL_BOOSTS` in favor of dynamic bundle-based resolution is excellent. It drastically reduces the maintenance burden when adding new bundles. |

### 4. `src/agents/interpreter/signal_accumulator.py`

| Lines | Comment |
| :--- | :--- |
| 586-623 | **[Logic]** The merge logic using unions for signals and dictionary merging for terminology is exactly what's needed for incremental state building. Minor point: ensure `ExtractionResult.missing_fields` is also correctly handled (currently it just takes `current.missing_fields`, which is correct as they should be re-calculated every turn). |

## Conclusion
This is a high-quality refactor that sets a strong foundation for more complex conversation flows. The code is well-structured, modular, and much easier to extend than the previous iteration.

**Status:** LGTM!

---

**Commit:** `378fb3cc91a9a756b97b390adefe4afea3b5706e`  
**Reviewer:** Senior Python Developer (Antigravity Assistant)  
**Date:** March 31, 2026

## Summary
This commit bridges the gap between the internal logic refactors and the external API. It introduces the "early preview" endpoint, adds a dedicated metadata router for bundles, and improves the overall robustness of the API layer through better dependency injection and startup validation.

## Detailed Review

### 1. `src/api/deps.py`

| Lines | Comment |
| :--- | :--- |
| 69-72 | **[Reliability]** Adding `catalog.validate()` and `catalog.validate_template_consistency()` inside the dependency provider is a great "fail-fast" mechanism. It ensures that the application won't serve requests if the bundle registry or templates are corrupted or inconsistent. |

### 2. `src/api/routers/preview.py`

| Lines | Comment |
| :--- | :--- |
| 170-201 | **[Clean Code]** Extracting `_run_preview_pipeline` is a good example of the DRY (Don't Repeat Yourself) principle. It makes adding the "early preview" endpoint much cleaner by reusing the same underlying generation logic. |
| 244-257 | **[User Experience]** The `generate_early_preview` endpoint is a significant UX improvement, allowing users to see a "draft" of their system before fully committing to a specific bundle. |

### 3. `src/api/routers/session.py`

| Lines | Comment |
| :--- | :--- |
| 316-333 | **[Type Safety]** Standardizing on `ConversationTurnRequest` and `TurnOptions` in the API handlers makes the interface between the routers and the orchestrators much more explicit and less prone to keyword-matching errors. |

### 4. `src/main.py`

| Lines | Comment |
| :--- | :--- |
| 415-441 | **[Nit]** The renaming of `app` to `application` and `settings` to `app_settings` is good for avoiding shadowed variables, though it adds a bit of noise to the diff. Consistency in naming across the project is always appreciated. |

## Conclusion
The API layer is now much better aligned with the underlying domain services. The addition of debug schemas and metadata endpoints suggests a forward-thinking approach to both troubleshooting and frontend integration.

**Status:** LGTM!


