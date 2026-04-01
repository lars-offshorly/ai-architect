from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from api.schemas.debug import ClassificationInfo, DebugInfo, RecommendationInfo


class SessionStartedResponse(BaseModel):
    status: Literal[
        "awaiting_input", "in_progress", "pending_confirmation", "ready_for_preview"
    ]
    session_id: str
    message: str | None = None
    question: str | None = None
    bundle_key: str | None = None
    slots: dict[str, object] = Field(default_factory=dict)
    debug: DebugInfo | None = None
    classification: ClassificationInfo | None = None
    recommendation: RecommendationInfo | None = None
    warning: str | None = Field(
        default=None,
        description=(
            "Present when the response was generated with incomplete information, "
            "such as an early preview before all required fields are filled."
        ),
    )
    preview_type: Literal["confirmed", "early"] | None = Field(
        default=None,
        description=(
            "Discriminator for preview readiness. "
            "'confirmed' = fully confirmed by the user. "
            "'early' = force-previewed with potentially incomplete data. "
            "None = not yet in a preview-ready state."
        ),
    )


class ConversationTurnResponse(BaseModel):
    status: Literal[
        "awaiting_input",
        "in_progress",
        "pending_confirmation",
        "ready_for_preview",
        "complete",
    ]
    session_id: str
    message: str | None = None
    question: str | None = None
    bundle_key: str | None = None
    slots: dict[str, object] = Field(default_factory=dict)
    debug: DebugInfo | None = None
    classification: ClassificationInfo | None = None
    recommendation: RecommendationInfo | None = None
    warning: str | None = Field(
        default=None,
        description=(
            "Present when the response was generated with incomplete information, "
            "such as an early preview before all required fields are filled."
        ),
    )
    preview_type: Literal["confirmed", "early"] | None = Field(
        default=None,
        description=(
            "Discriminator for preview readiness. "
            "'confirmed' = fully confirmed by the user. "
            "'early' = force-previewed with potentially incomplete data. "
            "None = not yet in a preview-ready state."
        ),
    )


class ErrorResponse(BaseModel):
    detail: str
