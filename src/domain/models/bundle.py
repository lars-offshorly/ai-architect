from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from domain.models.classification_result import ClassificationResult


class BundleSuggestion(BaseModel):
    bundle_key: str
    display_name: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""
    matched_signals: list[str] = Field(default_factory=list)
    variant_key: str | None = None
    variant_confidence: float | None = None


class SuggestedBundles(BaseModel):
    """DEPRECATED: Use ClassificationResult instead.

    This class is retained temporarily for backward compatibility.
    It will be removed after the deprecation period (target: 2025-05-07).

    Migration path:
        - Replace SuggestedBundles with ClassificationResult
        - Use BundleResolutionService.rank_to_classification() instead of rank()
    """

    session_id: str
    suggestions: list[BundleSuggestion] = Field(default_factory=list)
    top_bundle_key: str | None = None

    def __init__(self, **data: object) -> None:
        warnings.warn(
            "SuggestedBundles is deprecated. Use ClassificationResult instead. "
            "This class will be removed after 2025-05-07.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(**data)

    def to_classification_result(self) -> ClassificationResult:
        """Convert this SuggestedBundles to a ClassificationResult."""
        from domain.models.classification_result import ClassificationResult

        ranked = sorted(
            self.suggestions,
            key=lambda s: s.confidence,
            reverse=True,
        )
        top = ranked[0] if ranked else None
        score_gap = (
            ranked[0].confidence - ranked[1].confidence if len(ranked) > 1 else 0.0
        )

        return ClassificationResult(
            session_id=self.session_id,
            selected_bundle=top,
            ranked_candidates=ranked,
            confidence_status=(
                "proceed" if top and top.confidence >= 0.75 else "clarify"
            ),
            top_confidence=top.confidence if top else 0.0,
            score_gap=score_gap,
            missing_context=[],
            reasoning="Converted from deprecated SuggestedBundles",
        )

    def top(self) -> BundleSuggestion | None:
        if not self.suggestions:
            return None
        return max(self.suggestions, key=lambda s: s.confidence)

    def above_threshold(self, threshold: float) -> list[BundleSuggestion]:
        return [s for s in self.suggestions if s.confidence >= threshold]
