from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class SessionStartedResponse(BaseModel):
    status: Literal["awaiting_input", "in_progress", "pending_confirmation", "ready_for_preview"]
    session_id: str
    message: str | None = None
    question: str | None = None
    bundle_key: str | None = None
    slots: dict[str, object] = {}


class ConversationTurnResponse(BaseModel):
    status: Literal["awaiting_input", "in_progress", "pending_confirmation", "ready_for_preview", "complete"]
    session_id: str
    message: str | None = None
    question: str | None = None
    bundle_key: str | None = None
    slots: dict[str, object] = {}


class ErrorResponse(BaseModel):
    detail: str
