from __future__ import annotations

from catalog.bundle_catalog import BundleCatalog
from domain.models.bundle import BundleSuggestion
from domain.models.classification_result import ClassificationResult
from domain.models.extraction_result import ExtractionResult
from domain.models.recommendation_result import RecommendationResult


# pylint: disable=too-few-public-methods
class BundleRecommendationService:
    def __init__(self, catalog: BundleCatalog) -> None:
        self._catalog = catalog

    def recommend(
        self,
        classification: ClassificationResult,
        extracted: ExtractionResult,
        preselected_bundle_key: str | None = None,
    ) -> RecommendationResult:
        _ = extracted
        if preselected_bundle_key:
            # Resolve from preselected_bundle_key, not from potentially stale
            # classification.
            bundle = self._catalog.get(preselected_bundle_key)
            if bundle is None:
                # Fall back to classification.selected_bundle if preselected
                # bundle is not found.
                selected = classification.selected_bundle
                reasoning = (
                    f"Preselected bundle '{preselected_bundle_key}' "
                    "not found; using classification"
                )
            else:
                selected = BundleSuggestion(
                    bundle_key=bundle.bundle_key,
                    display_name=bundle.display_name,
                    confidence=1.0,
                    reasoning="Pre-selected by user",
                    matched_signals=[],
                )
                reasoning = "Bundle pre-selected by user"
            return RecommendationResult(
                session_id=classification.session_id,
                primary_bundle=selected,
                fallback_bundles=[],
                recommendation_status="preselected",
                inferred_modules=self._modules_for(selected),
                reasoning=reasoning,
            )

        if classification.confidence_status == "fallback_generic":
            selected = classification.selected_bundle
            return RecommendationResult(
                session_id=classification.session_id,
                primary_bundle=selected,
                fallback_bundles=[],
                recommendation_status="fallback_generic",
                inferred_modules=self._modules_for(selected),
                reasoning=classification.reasoning,
            )

        if classification.confidence_status == "proceed":
            selected = classification.selected_bundle
            return RecommendationResult(
                session_id=classification.session_id,
                primary_bundle=selected,
                fallback_bundles=[],
                recommendation_status="ready",
                inferred_modules=self._modules_for(selected),
                reasoning=classification.reasoning,
            )

        if classification.confidence_status == "suggest_alternatives":
            top = classification.selected_bundle
            fallbacks = classification.ranked_candidates[1:3]
            return RecommendationResult(
                session_id=classification.session_id,
                primary_bundle=top,
                fallback_bundles=fallbacks,
                recommendation_status="needs_clarification",
                inferred_modules=self._modules_for(top),
                reasoning="Multiple viable bundles; user choice required",
            )

        return RecommendationResult(
            session_id=classification.session_id,
            primary_bundle=classification.selected_bundle,
            fallback_bundles=[],
            recommendation_status="needs_clarification",
            inferred_modules=self._modules_for(classification.selected_bundle),
            reasoning=classification.reasoning or "Need more context from the user",
        )

    def _modules_for(self, suggestion: BundleSuggestion | None) -> list[str]:
        if suggestion is None:
            return []
        bundle = self._catalog.get(suggestion.bundle_key)
        if bundle is None:
            return []
        return list(bundle.default_modules)
