from __future__ import annotations

from datetime import datetime, timedelta, timezone

from domain.models.conversation import ConversationMessage, ConversationSummary


class ConversationRepository:
    def __init__(self, ttl_seconds: int = 3600) -> None:
        self._messages: dict[str, list[ConversationMessage]] = {}
        self._summaries: dict[str, ConversationSummary] = {}
        self._timestamps: dict[str, datetime] = {}
        self._ttl = timedelta(seconds=ttl_seconds)

    def _evict_expired(self) -> None:
        """
        Remove all messages and summaries for sessions whose last-activity
        timestamp is older than the TTL.  Called before every read and write
        so expired data is never returned or accidentally refreshed.
        """
        now = datetime.now(tz=timezone.utc)
        expired = [sid for sid, ts in self._timestamps.items() if now - ts > self._ttl]
        for sid in expired:
            self._messages.pop(sid, None)
            self._summaries.pop(sid, None)
            self._timestamps.pop(sid, None)

    def append_message(self, session_id: str, message: ConversationMessage) -> None:
        self._evict_expired()
        self._messages.setdefault(session_id, []).append(message)
        self._timestamps[session_id] = datetime.now(tz=timezone.utc)

    def get_messages(self, session_id: str) -> list[ConversationMessage]:
        self._evict_expired()
        return list(self._messages.get(session_id, []))

    def get_recent_messages(
        self, session_id: str, window: int
    ) -> list[ConversationMessage]:
        self._evict_expired()
        messages = self._messages.get(session_id, [])
        return list(messages[-window:])

    def save_summary(self, summary: ConversationSummary) -> None:
        self._evict_expired()
        self._summaries[summary.session_id] = summary
        self._timestamps[summary.session_id] = datetime.now(tz=timezone.utc)

    def get_summary(self, session_id: str) -> ConversationSummary | None:
        self._evict_expired()
        return self._summaries.get(session_id)

    def clear(self, session_id: str) -> None:
        self._messages.pop(session_id, None)
        self._summaries.pop(session_id, None)
        self._timestamps.pop(session_id, None)
