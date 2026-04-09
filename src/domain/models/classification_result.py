from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from domain.models.bundle import BundleSuggestion

ConfidenceStatus = Literal[
    "proceed",
    "suggest_alternatives",
    "clarify",
    "fallback_generic",
]


class ClassificationResult(BaseModel):
    session_id: str
    selected_bundle: BundleSuggestion | None = None
    ranked_candidates: list[BundleSuggestion] = Field(default_factory=list)
    confidence_status: ConfidenceStatus = "clarify"
    top_confidence: float = 0.0
    score_gap: float = 0.0
    missing_context: list[str] = Field(default_factory=list)
    reasoning: str = ""
