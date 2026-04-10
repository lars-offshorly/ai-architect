from __future__ import annotations

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers.bundles import router as bundles_router
from api.routers.health import router as health_router
from api.routers.mock import router as mock_router
from api.routers.preview import router as preview_router
from api.routers.session import router as session_router
from core.config import get_settings
from core.logging import get_logger

logger = get_logger(__name__)


def create_app() -> FastAPI:
    app_settings = get_settings()
    application = FastAPI(
        title="AI Architect API",
        version="0.1.0",
        description="AI-powered workspace onboarding pipeline.",
    )
    cors_origins = ["*"] if app_settings.DEBUG else []
    application.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(health_router)
    application.include_router(session_router)
    application.include_router(preview_router)
    application.include_router(bundles_router)
    if app_settings.ENABLE_MOCK_ENDPOINTS:
        application.include_router(mock_router)
        logger.info("Mock endpoints enabled")
    return application


app = create_app()

if __name__ == "__main__":
    run_settings = get_settings()
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=run_settings.DEBUG,
    )
