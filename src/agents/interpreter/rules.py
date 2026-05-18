"""Legacy signal-rule boosts — evaluation/non-runtime only.

Consumed by :mod:`agents.interpreter.classifier`, which is itself legacy.
The canonical runtime path does not invoke these helpers.
"""

from __future__ import annotations

from catalog.bundle_catalog import BundleDefinition


def detect_signals(
    text_fragments: list[str], bundles: list[BundleDefinition]
) -> list[str]:
    if not text_fragments or not bundles:
        return []
    lowered = " ".join(text_fragments).lower()
    detected: list[str] = []
    seen: set[str] = set()
    for bundle in bundles:
        for term in (
            *bundle.synonyms,
            *bundle.typical_entities,
            *bundle.typical_intents,
            *bundle.required_signals,
        ):
            t = term.casefold()
            if t not in seen and t in lowered:
                detected.append(term)
                seen.add(t)
    return detected


def apply_rule_boosts(
    candidates: list[dict[str, object]],
    bundles: list[BundleDefinition],
    detected_signals: list[str],
) -> list[dict[str, object]]:
    boost_map = {b.bundle_key: b.signal_boosts for b in bundles}
    lowered_signals = [s.casefold() for s in detected_signals]
    boosted: list[dict[str, object]] = []
    for candidate in candidates:
        key = str(candidate["bundle_key"])
        confidence_obj = candidate.get("confidence", 0.0)
        if isinstance(confidence_obj, (int, float, str)):
            try:
                confidence = float(confidence_obj)
            except ValueError:
                confidence = 0.0
        else:
            confidence = 0.0
        bundle_boosts = boost_map.get(key, {})
        total_boost = sum(
            bundle_boosts[boost_key]
            for boost_key in bundle_boosts
            if boost_key.casefold() in lowered_signals
        )
        updated = dict(candidate)
        updated["confidence"] = min(1.0, confidence + total_boost)
        boosted.append(updated)
    return boosted
