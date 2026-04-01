from __future__ import annotations

# pylint: disable=import-error,no-name-in-module
import pathlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from core import Database, get_logger, get_settings, pinecone_client

from .middleware import AuthMiddleware, RateLimitMiddleware
from .routes import health_router, onboarding_router

try:
    from .routers.bundles import router as BUNDLES_ROUTER
except ImportError:  # pragma: no cover - optional in legacy app wiring
    BUNDLES_ROUTER = None

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
    # Allow local file:// origins and localhost for the test UI
    cors_origins = ["*"] if settings.DEBUG else []
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(AuthMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.include_router(health_router)
    app.include_router(onboarding_router)
    if BUNDLES_ROUTER is not None:
        app.include_router(BUNDLES_ROUTER)

    if _FRONTEND_DIR.exists():
        app.mount("/static", StaticFiles(directory=_FRONTEND_DIR), name="static")

        @app.get("/")
        async def serve_index() -> FileResponse:
            return FileResponse(_FRONTEND_DIR / "index.html")

    return app
