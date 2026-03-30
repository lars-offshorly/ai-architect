from __future__ import annotations

from domain.models.conversation import ConversationMessage, ConversationSummary


class ConversationRepository:
    def __init__(self) -> None:
        self._messages: dict[str, list[ConversationMessage]] = {}
        self._summaries: dict[str, ConversationSummary] = {}

    def append_message(self, session_id: str, message: ConversationMessage) -> None:
        self._messages.setdefault(session_id, []).append(message)

    def get_messages(self, session_id: str) -> list[ConversationMessage]:
        return list(self._messages.get(session_id, []))

    def get_recent_messages(self, session_id: str, window: int) -> list[ConversationMessage]:
        messages = self._messages.get(session_id, [])
        return list(messages[-window:])

    def save_summary(self, summary: ConversationSummary) -> None:
        self._summaries[summary.session_id] = summary

    def get_summary(self, session_id: str) -> ConversationSummary | None:
        return self._summaries.get(session_id)

    def clear(self, session_id: str) -> None:
        self._messages.pop(session_id, None)
        self._summaries.pop(session_id, None)
