from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field


class Session(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    turn_count: int = 0
    confirmed: bool = False
    selected_bundle_key: str | None = None
    auth_token: str | None = None

    accumulated_extraction: dict | None = None
    latest_classification: dict | None = None
    latest_recommendation: dict | None = None
    clarification_turn_count: int = 0
