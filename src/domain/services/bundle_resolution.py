from __future__ import annotations

from ..models.bundle import BundleSuggestion, SuggestedBundles


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
                confidence=float(c.get("confidence", 0.0)),
                reasoning=str(c.get("reasoning", "")),
                matched_signals=list(c.get("matched_signals", [])),  # type: ignore[arg-type]
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
            confidence = float(candidate.get("confidence", 0.0))
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
