from __future__ import annotations

import pathlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from core import Database, get_logger, get_settings, pinecone_client

from .middleware import RateLimitMiddleware
from .middleware.auth import is_authenticated
from .routers.app import router as app_router
from .routers.bundles import router as bundles_router
from .routers.health import router as health_router
from .routers.preview import router as preview_router
from .routers.session import router as session_router

_FRONTEND_DIR = pathlib.Path(__file__).parent.parent / "frontend"

logger = get_logger(__name__)


@asynccontextmanager
async def _lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info("Initializing API dependencies")
    await Database.initialize()
    pinecone_client.initialize()
    try:
        yield
    finally:
        logger.info("Closing API dependencies")
        await pinecone_client.close()
        await Database.close()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="AI Architect API",
        version="0.1.0",
        lifespan=_lifespan,
    )
    cors_origins = [
        "https://ai-architect.idealforliving.com",
        "http://localhost:3000",
        "http://localhost:3001",
    ]
    if settings.DEBUG:
        cors_origins.append("*")
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    _auth = [Depends(is_authenticated)]

    app.include_router(health_router)
    app.include_router(session_router, dependencies=_auth)
    app.include_router(preview_router, dependencies=_auth)
    app.include_router(bundles_router, dependencies=_auth)
    app.include_router(app_router, dependencies=_auth)

    if settings.ENABLE_MOCK_ENDPOINTS:
        from .routers.mock import router as mock_router

        app.include_router(mock_router, dependencies=_auth)
        logger.info("Mock endpoints enabled")

    if _FRONTEND_DIR.exists():
        app.mount("/static", StaticFiles(directory=_FRONTEND_DIR), name="static")

        @app.get("/")  # intentionally unprotected: SPA handles auth client-side
        async def serve_index() -> FileResponse:
            return FileResponse(_FRONTEND_DIR / "index.html")

    return app
