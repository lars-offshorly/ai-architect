from __future__ import annotations

from pydantic import BaseModel, Field


class BundleSuggestion(BaseModel):
    bundle_key: str
    display_name: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""
    matched_signals: list[str] = Field(default_factory=list)


class SuggestedBundles(BaseModel):
    session_id: str
    suggestions: list[BundleSuggestion] = Field(default_factory=list)
    top_bundle_key: str | None = None

    def top(self) -> BundleSuggestion | None:
        if not self.suggestions:
            return None
        return max(self.suggestions, key=lambda s: s.confidence)

    def above_threshold(self, threshold: float) -> list[BundleSuggestion]:
        return [s for s in self.suggestions if s.confidence >= threshold]
