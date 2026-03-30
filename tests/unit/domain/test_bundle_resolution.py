from __future__ import annotations

from domain.services.bundle_resolution import BundleResolutionService


def _make_candidates(*bundle_keys_and_confidences: tuple[str, float]) -> list[dict[str, object]]:
    return [
        {
            "bundle_key": key,
            "display_name": key,
            "confidence": conf,
            "reasoning": "",
            "matched_signals": [],
        }
        for key, conf in bundle_keys_and_confidences
    ]


def test_rank_returns_sorted_by_confidence() -> None:
    service = BundleResolutionService()
    candidates = _make_candidates(("hr_hub", 0.4), ("project_ops", 0.8), ("generic", 0.2))
    result = service.rank("session-1", candidates)
    keys = [s.bundle_key for s in result.suggestions]
    assert keys == ["project_ops", "hr_hub", "generic"]


def test_rank_sets_top_bundle_key() -> None:
    service = BundleResolutionService()
    candidates = _make_candidates(("hr_hub", 0.9), ("project_ops", 0.5))
    result = service.rank("session-1", candidates)
    assert result.top_bundle_key == "hr_hub"


def test_rank_empty_candidates() -> None:
    service = BundleResolutionService()
    result = service.rank("session-1", [])
    assert result.suggestions == []
    assert result.top_bundle_key is None


def test_top_returns_highest_confidence() -> None:
    service = BundleResolutionService()
    candidates = _make_candidates(("hr_hub", 0.9), ("project_ops", 0.5))
    result = service.rank("session-1", candidates)
    top = result.top()
    assert top is not None
    assert top.bundle_key == "hr_hub"
    assert top.confidence == 0.9


def test_above_threshold_filters_correctly() -> None:
    service = BundleResolutionService()
    candidates = _make_candidates(("hr_hub", 0.9), ("project_ops", 0.5), ("generic", 0.3))
    result = service.rank("session-1", candidates)
    above = result.above_threshold(0.6)
    assert len(above) == 1
    assert above[0].bundle_key == "hr_hub"
