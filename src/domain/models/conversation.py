from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class ConversationMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ConversationSummary(BaseModel):
    session_id: str
    summary_text: str
    message_count: int
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
