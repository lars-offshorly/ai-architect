from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from domain.models.bundle import BundleSuggestion

RecommendationStatus = Literal[
    "ready",
    "needs_clarification",
    "fallback_generic",
    "preselected",
]


class RecommendationResult(BaseModel):
    session_id: str
    primary_bundle: BundleSuggestion | None = None
    fallback_bundles: list[BundleSuggestion] = Field(default_factory=list)
    recommendation_status: RecommendationStatus = "needs_clarification"
    inferred_modules: list[str] = Field(default_factory=list)
    reasoning: str = ""
