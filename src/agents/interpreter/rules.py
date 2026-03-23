from __future__ import annotations

_SIGNAL_MAP: dict[str, list[str]] = {
    "hr_hub": [
        "leave", "employee", "hr", "human resources", "onboarding", "offboarding",
        "payroll", "attendance", "recruitment", "people ops", "talent",
    ],
    "project_ops": [
        "project", "milestone", "deadline", "sprint", "delivery", "consulting",
        "client", "timeline", "roadmap", "scope", "implementation",
    ],
    "asset_mgmt": [
        "asset", "equipment", "machine", "vehicle", "fleet", "facility",
        "maintenance", "inventory", "warehouse", "hardware", "physical",
    ],
    "field_service": [
        "technician", "field", "dispatch", "work order", "on-site", "repair",
        "zone", "scheduling", "installation", "service call",
    ],
}

_SIGNAL_BOOSTS: dict[str, dict[str, float]] = {
    "hr_hub": {
        "leave": 0.15,
        "employee": 0.10,
        "hr": 0.20,
        "onboarding": 0.15,
        "people ops": 0.20,
        "attendance": 0.15,
    },
    "project_ops": {
        "project": 0.15,
        "milestone": 0.15,
        "sprint": 0.20,
        "consulting": 0.15,
        "delivery": 0.10,
    },
    "asset_mgmt": {
        "asset": 0.20,
        "equipment": 0.15,
        "maintenance": 0.15,
        "fleet": 0.20,
        "warehouse": 0.15,
    },
    "field_service": {
        "technician": 0.20,
        "dispatch": 0.20,
        "work order": 0.15,
        "field": 0.10,
        "on-site": 0.15,
    },
}


def detect_signals(text: str) -> list[str]:
    lowered = text.lower()
    detected: list[str] = []
    for signals in _SIGNAL_MAP.values():
        for signal in signals:
            if signal in lowered and signal not in detected:
                detected.append(signal)
    return detected


def build_signal_boosts() -> dict[str, dict[str, float]]:
    return dict(_SIGNAL_BOOSTS)


def apply_rule_boosts(
    candidates: list[dict[str, object]],
    boosts: dict[str, dict[str, float]],
    detected_signals: list[str],
) -> list[dict[str, object]]:
    boosted: list[dict[str, object]] = []
    for candidate in candidates:
        key = str(candidate["bundle_key"])
        confidence = float(candidate.get("confidence", 0.0))
        bundle_boosts = boosts.get(key, {})
        total_boost = sum(
            bundle_boosts[signal]
            for signal in detected_signals
            if signal in bundle_boosts
        )
        updated = dict(candidate)
        updated["confidence"] = min(1.0, confidence + total_boost)
        boosted.append(updated)
    return boosted
