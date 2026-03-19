from __future__ import annotations

from fastapi import APIRouter, status
from starlette.responses import JSONResponse

from core import Database, pinecone_client

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> JSONResponse:
    db_healthy = await Database.health_check()
    pinecone_healthy = await pinecone_client.health_check()
    checks = {
        "database": db_healthy,
        "pinecone": pinecone_healthy,
    }
    is_healthy = all(checks.values())
    payload = {
        "status": "ok" if is_healthy else "degraded",
        "checks": checks,
    }
    status_code = (
        status.HTTP_200_OK
        if is_healthy
        else status.HTTP_503_SERVICE_UNAVAILABLE
    )
    return JSONResponse(status_code=status_code, content=payload)
