from __future__ import annotations

# pylint: disable=duplicate-code
from collections.abc import Sequence

from ..models.bundle import BundleSuggestion, SuggestedBundles


def _to_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def _to_str_list(value: object) -> list[str]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [str(item) for item in value]
    return []


class BundleResolutionService:
    def rank(
        self,
        session_id: str,
        scored_candidates: list[dict[str, object]],
    ) -> SuggestedBundles:
        suggestions = [
            BundleSuggestion(
                bundle_key=str(c["bundle_key"]),
                display_name=str(c.get("display_name", c["bundle_key"])),
                confidence=_to_float(c.get("confidence", 0.0)),
                reasoning=str(c.get("reasoning", "")),
                matched_signals=_to_str_list(c.get("matched_signals", [])),
            )
            for c in scored_candidates
        ]
        suggestions.sort(key=lambda s: s.confidence, reverse=True)
        top_key = suggestions[0].bundle_key if suggestions else None
        return SuggestedBundles(
            session_id=session_id,
            suggestions=suggestions,
            top_bundle_key=top_key,
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
