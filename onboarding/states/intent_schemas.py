from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TurnClassification(BaseModel):
    turn_type: Literal[
        "new_onboarding",
        "clarification_answer",
        "bundle_confirmation",
        "bundle_rejection",
        "out_of_scope",
        "harmful",
    ]
    extracted_answer: str = ""


class OnboardingIntents(BaseModel):
    raw_intent: str
    entity_type: Literal["people", "asset", "work", "other"]
    bundle: str | None = None
    inferred_modules: list[str] = Field(default_factory=list)
    explicit_modules: list[str] = Field(default_factory=list)
    industry_hint: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
