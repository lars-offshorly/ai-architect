from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field, ValidationInfo, field_validator

from domain.models.bundle import BundleSuggestion
from domain.models.classification_result import ClassificationResult
from domain.models.extraction_result import ExtractionResult
from domain.models.recommendation_result import RecommendationResult


class Session(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    turn_count: int = 0
    confirmed: bool = False
    selected_bundle_key: str | None = None
    auth_token: str | None = None

    accumulated_extraction: ExtractionResult | None = None
    latest_classification: ClassificationResult | None = None
    latest_recommendation: RecommendationResult | None = None
    clarification_turn_count: int = 0
    preselected_intent: str | None = None
    preselected_bundle_key: str | None = None

    @field_validator("latest_classification", mode="before")
    @classmethod
    def _coerce_latest_classification(
        cls,
        value: object,
        info: ValidationInfo,
    ) -> object:
        if value is None or isinstance(value, ClassificationResult):
            return value

        if not isinstance(value, dict):
            return value

        session_id = str(value.get("session_id") or info.data.get("session_id") or "")

        selected_bundle = value.get("selected_bundle")
        top_bundle_key = value.get("top_bundle_key")
        if (
            selected_bundle is None
            and isinstance(top_bundle_key, str)
            and top_bundle_key
        ):
            selected_bundle = BundleSuggestion(
                bundle_key=top_bundle_key,
                display_name=top_bundle_key,
                confidence=float(value.get("top_confidence") or 0.0),
                reasoning="Coerced from top_bundle_key payload",
                matched_signals=[],
            )

        confidence_status = value.get("confidence_status")
        valid_statuses = {
            "proceed",
            "suggest_alternatives",
            "clarify",
            "fallback_generic",
        }
        if confidence_status not in valid_statuses:
            confidence_status = "proceed" if selected_bundle is not None else "clarify"

        suggestions = list(value.get("suggestions") or [])
        top_confidence_raw = value.get("top_confidence")
        if top_confidence_raw is None and suggestions:
            first = suggestions[0]
            if isinstance(first, dict):
                top_confidence_raw = first.get("confidence")

        return ClassificationResult(
            session_id=session_id,
            selected_bundle=selected_bundle,
            ranked_candidates=list(value.get("ranked_candidates") or []),
            confidence_status=confidence_status,
            top_confidence=float(top_confidence_raw or 0.0),
            score_gap=float(value.get("score_gap") or 0.0),
            missing_context=list(value.get("missing_context") or []),
            reasoning=str(value.get("reasoning") or ""),
        )
