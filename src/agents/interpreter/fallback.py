from __future__ import annotations

from agents.replier.clarification import is_critical
from catalog.bundle_catalog import BundleCatalog
from domain.models.bundle import BundleSuggestion
from domain.models.classification_result import ClassificationResult
from domain.models.extraction_result import ExtractionResult


# pylint: disable=too-few-public-methods
class FallbackHandler:
    def __init__(
        self,
        catalog: BundleCatalog,
        proceed_threshold: float = 0.75,
        suggest_threshold: float = 0.50,
        score_gap_minimum: float = 0.15,
        max_clarification_turns: int = 3,
        # These constructor params are intentionally explicit and configurable.
        # pylint: disable=too-many-arguments,too-many-positional-arguments
    ) -> None:
        self._catalog = catalog
        self._proceed_threshold = proceed_threshold
        self._suggest_threshold = suggest_threshold
        self._score_gap_minimum = score_gap_minimum
        self._max_clarification_turns = max_clarification_turns

    def apply(
        self,
        classification: ClassificationResult,
        extracted: ExtractionResult,
        clarification_turn_count: int,
    ) -> ClassificationResult:
        critical_missing = [
            field for field in extracted.missing_fields if is_critical(field)
        ]
        missing_context = [field.value for field in extracted.missing_fields]
        top = (
            classification.ranked_candidates[0]
            if classification.ranked_candidates
            else None
        )
        score_gap = _score_gap(classification.ranked_candidates)

        # After the first clarification question has already been asked, let
        # confidence win: if the bundle is clear enough to proceed, don't force
        # another round just because optional signals are still missing.
        if (
            clarification_turn_count >= 1
            and top is not None
            and self._is_proceed(top.confidence, score_gap)
        ):
            return classification.model_copy(
                update={
                    "selected_bundle": top,
                    "confidence_status": "proceed",
                    "top_confidence": top.confidence,
                    "score_gap": score_gap,
                    "missing_context": missing_context,
                    "reasoning": "",
                }
            )

        # On the very first turn, missing critical fields take priority so we
        # always collect the minimum context before committing to a bundle.
        if critical_missing:
            return classification.model_copy(
                update={
                    "selected_bundle": top,
                    "confidence_status": "clarify",
                    "top_confidence": top.confidence if top is not None else 0.0,
                    "score_gap": score_gap,
                    "missing_context": missing_context,
                    "reasoning": "",
                }
            )

        if top is not None and self._is_proceed(top.confidence, score_gap):
            return classification.model_copy(
                update={
                    "selected_bundle": top,
                    "confidence_status": "proceed",
                    "top_confidence": top.confidence,
                    "score_gap": score_gap,
                    "missing_context": missing_context,
                    "reasoning": "",
                }
            )

        if top is not None and top.confidence >= self._suggest_threshold:
            # Respect the same turn budget as clarify so suggest_alternatives
            # can never loop indefinitely. Once the budget is exhausted, accept
            # the best candidate rather than asking the same question again.
            if clarification_turn_count >= self._max_clarification_turns:
                return classification.model_copy(
                    update={
                        "selected_bundle": top,
                        "confidence_status": "proceed",
                        "top_confidence": top.confidence,
                        "score_gap": score_gap,
                        "missing_context": missing_context,
                        "reasoning": "",
                    }
                )
            return classification.model_copy(
                update={
                    "selected_bundle": top,
                    "confidence_status": "suggest_alternatives",
                    "top_confidence": top.confidence,
                    "score_gap": score_gap,
                    "missing_context": missing_context,
                    "reasoning": "",
                }
            )

        # Clarification budget check (no critical_missing at this point)
        if clarification_turn_count < self._max_clarification_turns:
            return classification.model_copy(
                update={
                    "selected_bundle": top,
                    "confidence_status": "clarify",
                    "top_confidence": top.confidence if top is not None else 0.0,
                    "score_gap": score_gap,
                    "missing_context": missing_context,
                    "reasoning": "",
                }
            )

        fallback = self._fallback_suggestion()
        return classification.model_copy(
            update={
                "selected_bundle": fallback,
                "confidence_status": "fallback_generic",
                "top_confidence": top.confidence if top is not None else 0.0,
                "score_gap": score_gap,
                "missing_context": missing_context,
                "reasoning": "",
            }
        )

    def _is_proceed(self, top_confidence: float, score_gap: float) -> bool:
        return (
            top_confidence >= self._proceed_threshold
            and score_gap >= self._score_gap_minimum
        )

    def _fallback_suggestion(self) -> BundleSuggestion:
        fallback_bundle = self._catalog.get_fallback()
        return BundleSuggestion(
            bundle_key=fallback_bundle.bundle_key,
            display_name=fallback_bundle.display_name,
            confidence=0.0,
            reasoning="Generic fallback",
            matched_signals=[],
        )


def _score_gap(ranked_candidates: list[BundleSuggestion]) -> float:
    if not ranked_candidates:
        return 0.0
    if len(ranked_candidates) == 1:
        return ranked_candidates[0].confidence
    return ranked_candidates[0].confidence - ranked_candidates[1].confidence
