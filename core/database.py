from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool

from .logging_config import get_logger
from .settings import get_settings

logger = get_logger(__name__)


class Database:
    _pool: AsyncConnectionPool | None = None

    @classmethod
    async def initialize(cls) -> None:
        if cls._pool is None:
            settings = get_settings()
            if not settings.DATABASE_URL:
                raise ValueError(
                    "DATABASE_URL is not set. Please check your .env file.",
                )
            db_url = settings.DATABASE_URL.replace(
                "postgresql+asyncpg://",
                "postgresql://",
            )

            pool_size = getattr(settings, "DB_POOL_MAX_SIZE", 20)

            cls._pool = AsyncConnectionPool(
                conninfo=db_url,
                max_size=pool_size,
                open=False,
            )
            await cls._pool.open()

        async with cls._pool.connection() as conn:
            await conn.set_autocommit(True)
            checkpointer = AsyncPostgresSaver(conn)
            await checkpointer.setup()

    @classmethod
    @asynccontextmanager
    async def get_checkpointer(cls) -> AsyncIterator[AsyncPostgresSaver]:
        if cls._pool is None:
            raise RuntimeError(
                "Database not initialized. Call Database.initialize() first.",
            )
        checkpointer = AsyncPostgresSaver(cls._pool)
        yield checkpointer

    @classmethod
    async def close(cls) -> None:
        if cls._pool:
            await cls._pool.close()
            cls._pool = None

    @classmethod
    async def health_check(cls) -> bool:
        if cls._pool is None:
            await cls.initialize()

        if cls._pool is None:
            return False

        try:
            async with cls._pool.connection() as conn:
                await conn.execute("SELECT 1")
            return True
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Database connection check failed: %s", e)
            return False

    @classmethod
    async def check_connection(cls) -> bool:
        return await cls.health_check()
