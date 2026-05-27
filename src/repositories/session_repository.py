from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.exceptions import SessionNotFoundError
from domain.models.session import Session


class SessionRepository:
    def __init__(self, ttl_seconds: int = 3600) -> None:
        self._store: dict[str, Session] = {}
        self._timestamps: dict[str, datetime] = {}
        self._ttl = timedelta(seconds=ttl_seconds)

    def _evict_expired(self) -> None:
        """
        Remove sessions whose last-activity timestamp is older than the TTL.
        Called before each mutating operation so expired sessions are cleared
        lazily without a background task.
        """
        now = datetime.now(tz=timezone.utc)
        expired = [
            sid for sid, ts in self._timestamps.items() if now - ts > self._ttl
        ]
        for sid in expired:
            self._store.pop(sid, None)
            self._timestamps.pop(sid, None)

    def save(self, session: Session) -> None:
        self._evict_expired()
        self._store[session.session_id] = session
        self._timestamps[session.session_id] = datetime.now(tz=timezone.utc)

    def get(self, session_id: str) -> Session:
        session = self._store.get(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)
        self._timestamps[session_id] = datetime.now(tz=timezone.utc)
        return session

    def exists(self, session_id: str) -> bool:
        self._evict_expired()
        return session_id in self._store

    def delete(self, session_id: str) -> None:
        self._store.pop(session_id, None)
        self._timestamps.pop(session_id, None)
