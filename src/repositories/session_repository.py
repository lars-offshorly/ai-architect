from __future__ import annotations

from core.exceptions import SessionNotFoundError
from domain.models.session import Session


class SessionRepository:
    def __init__(self) -> None:
        self._store: dict[str, Session] = {}

    def save(self, session: Session) -> None:
        self._store[session.session_id] = session

    def get(self, session_id: str) -> Session:
        session = self._store.get(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)
        return session

    def exists(self, session_id: str) -> bool:
        return session_id in self._store

    def delete(self, session_id: str) -> None:
        self._store.pop(session_id, None)
