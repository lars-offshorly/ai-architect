from __future__ import annotations

from fastapi import APIRouter

from core import Database, pinecone_client

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, object]:
    return {
        "status": "ok",
        "checks": {
            "database": await Database.health_check(),
            "pinecone": await pinecone_client.health_check(),
        },
    }
