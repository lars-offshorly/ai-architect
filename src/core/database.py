from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.checkpoint.memory import InMemorySaver


class Database:
    """Minimal async database facade used by onboarding/API wiring."""

    _memory = InMemorySaver()

    @classmethod
    async def initialize(cls) -> None:
        return None

    @classmethod
    async def close(cls) -> None:
        return None

    @classmethod
    async def health_check(cls) -> bool:
        return True

    @classmethod
    @asynccontextmanager
    async def get_checkpointer(cls) -> AsyncIterator[InMemorySaver]:
        yield cls._memory
