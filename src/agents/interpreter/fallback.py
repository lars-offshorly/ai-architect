from __future__ import annotations

from agents.replier.clarification import is_critical
from domain.models.bundle import BundleSuggestion
from domain.models.classification_result import ClassificationResult
from domain.models.extraction_result import ExtractionResult


# pylint: disable=too-few-public-methods
class FallbackHandler:
    def __init__(
        self,
        proceed_threshold: float = 0.75,
        suggest_threshold: float = 0.50,
        score_gap_minimum: float = 0.15,
        max_clarification_turns: int = 3,
        # These constructor params are intentionally explicit and configurable.
        # pylint: disable=too-many-arguments,too-many-positional-arguments
    ) -> None:
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

        # Check critical missing fields FIRST, before confidence checks
        # This ensures missing critical info triggers clarification
        # regardless of confidence.
        if critical_missing:
            return classification.model_copy(
                update={
                    "selected_bundle": top,
                    "confidence_status": "clarify",
                    "top_confidence": top.confidence if top is not None else 0.0,
                    "score_gap": score_gap,
                    "missing_context": missing_context,
                    "reasoning": "Critical fields missing",
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
                    "reasoning": "High confidence with sufficient score gap",
                }
            )

        if top is not None and top.confidence >= self._suggest_threshold:
            return classification.model_copy(
                update={
                    "selected_bundle": top,
                    "confidence_status": "suggest_alternatives",
                    "top_confidence": top.confidence,
                    "score_gap": score_gap,
                    "missing_context": missing_context,
                    "reasoning": "Moderate confidence or tie-gap ambiguity",
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
                    "reasoning": "Clarification budget available",
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
                "reasoning": "Clarification budget exhausted; using generic fallback",
            }
        )

    def _is_proceed(self, top_confidence: float, score_gap: float) -> bool:
        return (
            top_confidence >= self._proceed_threshold
            and score_gap >= self._score_gap_minimum
        )

    def _fallback_suggestion(self) -> BundleSuggestion:
        return BundleSuggestion(
            bundle_key="generic",
            display_name="Custom Workspace",
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
