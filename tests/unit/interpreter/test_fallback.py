from __future__ import annotations

from pathlib import Path

from agents.interpreter.fallback import FallbackHandler
from catalog.bundle_catalog import BundleCatalog
from domain.enums.missing_field_type import MissingFieldType
from domain.models.bundle import BundleSuggestion
from domain.models.classification_result import ClassificationResult
from domain.models.extraction_result import ExtractionResult

REGISTRY_PATH = (
    Path(__file__).resolve().parents[3] / "src/templates/bundle_registry.yaml"
)


def _classification(
    *,
    confidence: float,
    score_gap: float,
    bundle_key: str = "hr_management",
) -> ClassificationResult:
    top = BundleSuggestion(
        bundle_key=bundle_key,
        display_name=bundle_key,
        confidence=confidence,
    )
    second = BundleSuggestion(
        bundle_key="project_mgmt",
        display_name="project_mgmt",
        confidence=max(0.0, confidence - score_gap),
    )
    return ClassificationResult(
        session_id="s1",
        selected_bundle=top,
        ranked_candidates=[top, second],
        top_confidence=confidence,
        score_gap=score_gap,
    )


def _extraction(*, missing: list[MissingFieldType] | None = None) -> ExtractionResult:
    return ExtractionResult(session_id="s1", missing_fields=missing or [])


def test_fallback_proceed_branch() -> None:
    handler = FallbackHandler(BundleCatalog(REGISTRY_PATH))
    result = handler.apply(
        _classification(confidence=0.9, score_gap=0.3),
        _extraction(),
        0,
    )
    assert result.confidence_status == "proceed"


def test_fallback_suggest_alternatives_for_tie_gap() -> None:
    handler = FallbackHandler(BundleCatalog(REGISTRY_PATH))
    result = handler.apply(
        _classification(confidence=0.8, score_gap=0.05),
        _extraction(),
        0,
    )
    assert result.confidence_status == "suggest_alternatives"


def test_fallback_critical_missing_fields_clarify() -> None:
    handler = FallbackHandler(BundleCatalog(REGISTRY_PATH))
    extraction = _extraction(missing=[MissingFieldType.PRIMARY_USE_CASE])
    result = handler.apply(
        _classification(confidence=0.3, score_gap=0.1),
        extraction,
        0,
    )
    assert result.confidence_status == "clarify"


def test_fallback_budget_exhaustion_uses_generic() -> None:
    handler = FallbackHandler(BundleCatalog(REGISTRY_PATH))
    result = handler.apply(
        _classification(confidence=0.2, score_gap=0.01),
        _extraction(),
        99,
    )
    assert result.confidence_status == "fallback_generic"
    assert result.selected_bundle is not None
    assert result.selected_bundle.bundle_key == "generic"
