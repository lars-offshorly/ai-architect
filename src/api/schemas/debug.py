from __future__ import annotations

from pydantic import BaseModel, Field


class DebugInfo(BaseModel):
    extracted_keywords: list[str] = Field(default_factory=list)
    extracted_entities: list[str] = Field(default_factory=list)
    extracted_intents: list[str] = Field(default_factory=list)
    extracted_workflow_hints: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    personalization: dict[str, object] = Field(default_factory=dict)


class BundleCandidateInfo(BaseModel):
    bundle_key: str
    display_name: str
    confidence: float
    reasoning: str = ""
    matched_signals: list[str] = Field(default_factory=list)


class ClassificationInfo(BaseModel):
    confidence_status: str
    top_bundle_key: str | None = None
    top_confidence: float = 0.0
    score_gap: float = 0.0
    missing_context: list[str] = Field(default_factory=list)
    reasoning: str = ""
    ranked_candidates: list[BundleCandidateInfo] = Field(default_factory=list)


class RecommendationInfo(BaseModel):
    recommendation_status: str
    primary_bundle_key: str | None = None
    fallback_bundle_keys: list[str] = Field(default_factory=list)
    inferred_modules: list[str] = Field(default_factory=list)
    reasoning: str = ""
