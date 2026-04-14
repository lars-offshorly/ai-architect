from __future__ import annotations

import warnings
from typing import cast

from domain.models.bundle import BundleSuggestion
from domain.models.classification_result import ClassificationResult


def _to_float(value: object) -> float:
    if not isinstance(value, (int, float, str, bytes, bytearray)):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


class BundleResolutionService:
    def rank(
        self,
        session_id: str,
        scored_candidates: list[dict[str, object]],
    ) -> object:  # Returns SuggestedBundles for backward compatibility
        """DEPRECATED: Use rank_to_classification() instead.

        This method is retained for backward compatibility but will be removed
        after the deprecation period (target: 2025-05-07).
        """
        warnings.warn(
            "rank() is deprecated. Use rank_to_classification() instead. "
            "This method will be removed after 2025-05-07.",
            DeprecationWarning,
            stacklevel=2,
        )
        from domain.models.bundle import SuggestedBundles

        suggestions = [
            BundleSuggestion(
                bundle_key=str(c["bundle_key"]),
                display_name=str(c.get("display_name", c["bundle_key"])),
                confidence=_to_float(c.get("confidence", 0.0)),
                reasoning=str(c.get("reasoning", "")),
                matched_signals=list(cast(list[object], c.get("matched_signals", []))),
            )
            for c in scored_candidates
        ]
        suggestions.sort(key=lambda s: s.confidence, reverse=True)
        top_key = suggestions[0].bundle_key if suggestions else None
        # Suppress the deprecation warning when creating SuggestedBundles internally
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            return SuggestedBundles(
                session_id=session_id,
                suggestions=suggestions,
                top_bundle_key=top_key,
            )

    def rank_to_classification(
        self,
        session_id: str,
        scored_candidates: list[dict[str, object]],
    ) -> ClassificationResult:
        """Rank candidates and return a ClassificationResult.

        This is the recommended replacement for the deprecated rank() method.
        Returns a ClassificationResult directly instead of SuggestedBundles.
        """
        suggestions = [
            BundleSuggestion(
                bundle_key=str(c["bundle_key"]),
                display_name=str(c.get("display_name", c["bundle_key"])),
                confidence=_to_float(c.get("confidence", 0.0)),
                reasoning=str(c.get("reasoning", "")),
                matched_signals=list(cast(list[object], c.get("matched_signals", []))),
            )
            for c in scored_candidates
        ]
        suggestions.sort(key=lambda s: s.confidence, reverse=True)

        ranked = suggestions
        top = ranked[0] if ranked else None
        score_gap = (
            ranked[0].confidence - ranked[1].confidence if len(ranked) > 1 else 0.0
        )

        # Determine confidence status based on top confidence
        confidence_status: str = "clarify"
        if top:
            if top.confidence >= 0.75:
                confidence_status = "proceed"
            elif top.confidence >= 0.50:
                confidence_status = "suggest_alternatives"
            else:
                confidence_status = "fallback_generic"

        return ClassificationResult(
            session_id=session_id,
            selected_bundle=top,
            ranked_candidates=ranked,
            confidence_status=confidence_status,  # type: ignore[arg-type]
            top_confidence=top.confidence if top else 0.0,
            score_gap=score_gap,
            missing_context=[],
            reasoning="Bundle ranking from BundleResolutionService",
        )

    def apply_rule_boosts(
        self,
        candidates: list[dict[str, object]],
        signal_boosts: dict[str, dict[str, float]],
        detected_signals: list[str],
    ) -> list[dict[str, object]]:
        boosted = []
        for candidate in candidates:
            key = str(candidate["bundle_key"])
            confidence = _to_float(candidate.get("confidence", 0.0))
            boosts_for_bundle = signal_boosts.get(key, {})
            total_boost = sum(
                boosts_for_bundle[signal]
                for signal in detected_signals
                if signal in boosts_for_bundle
            )
            updated = dict(candidate)
            updated["confidence"] = min(1.0, confidence + total_boost)
            boosted.append(updated)
        return boosted
