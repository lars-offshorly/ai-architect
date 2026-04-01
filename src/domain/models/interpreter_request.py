from __future__ import annotations

from dataclasses import dataclass

from domain.models.conversation import ConversationMessage
from domain.models.extraction_result import ExtractionResult


@dataclass(slots=True)
class InterpreterRequest:
    session_id: str
    user_message: str
    history: list[ConversationMessage]
    accumulated_extraction: ExtractionResult | None = None
    summary: str = ""
    preselected_intent: str | None = None
