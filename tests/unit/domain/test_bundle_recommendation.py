from __future__ import annotations

from pathlib import Path

from catalog.bundle_catalog import BundleCatalog
from domain.models.bundle import BundleSuggestion
from domain.models.classification_result import ClassificationResult
from domain.models.extraction_result import ExtractionResult
from domain.services.bundle_recommendation import BundleRecommendationService

REGISTRY_PATH = (
    Path(__file__).resolve().parents[3] / "src/templates/bundle_registry.yaml"
)


def _classification(status: str) -> ClassificationResult:
    top = BundleSuggestion(
        bundle_key="hr_management",
        display_name="HR Management",
        confidence=0.8,
    )
    alt = BundleSuggestion(
        bundle_key="project_mgmt",
        display_name="Project Management",
        confidence=0.7,
    )
    return ClassificationResult(
        session_id="s1",
        selected_bundle=top,
        ranked_candidates=[top, alt],
        confidence_status=status,
        top_confidence=0.8,
        score_gap=0.1,
    )


def test_recommend_ready_from_proceed() -> None:
    service = BundleRecommendationService(BundleCatalog(REGISTRY_PATH))
    result = service.recommend(
        _classification("proceed"),
        ExtractionResult(session_id="s1"),
    )
    assert result.recommendation_status == "ready"
    assert result.primary_bundle is not None


def test_recommend_suggest_alternatives_keeps_fallbacks() -> None:
    service = BundleRecommendationService(BundleCatalog(REGISTRY_PATH))
    result = service.recommend(
        _classification("suggest_alternatives"),
        ExtractionResult(session_id="s1"),
    )
    assert result.recommendation_status == "needs_clarification"
    assert len(result.fallback_bundles) == 1


def test_recommend_preselected_override() -> None:
    service = BundleRecommendationService(BundleCatalog(REGISTRY_PATH))
    result = service.recommend(
        _classification("proceed"),
        ExtractionResult(session_id="s1"),
        preselected_bundle_key="hr_management",
    )
    assert result.recommendation_status == "preselected"
