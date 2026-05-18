from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.security import HTTPBearer as FastAPIHTTPBearer
from pydantic import BaseModel
from redis import asyncio as aioredis

from core import get_logger, get_settings

logger = get_logger(__name__)

# Django cache namespace prefix used by the upstream auth service.
_AUTH_CACHE_KEY_PREFIX = ":1:"
_REDIS_CLIENT: aioredis.Redis | None = None


class UserSchema(BaseModel):
    id: int
    role_permissions: dict[str, Any]  # shape controlled by external auth service
    token: str


def _get_redis_client() -> aioredis.Redis:
    global _REDIS_CLIENT  # pylint: disable=global-statement
    if _REDIS_CLIENT is None:
        settings = get_settings()
        _REDIS_CLIENT = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _REDIS_CLIENT


def _parse_user_from_cache(raw: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(json.loads(raw))
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        logger.warning("Failed to parse cached auth data: %s", exc)
        return None
    if not isinstance(payload, dict):
        return None
    user = payload.get("user", {})
    if not isinstance(user, dict):
        return None
    return user


async def _lookup_token(token: str) -> dict[str, Any] | None:
    redis = _get_redis_client()
    cache_key = f"{_AUTH_CACHE_KEY_PREFIX}{token}"
    try:
        cached = await redis.get(cache_key)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.warning("Redis auth lookup failed: %s", exc)
        return None
    if not cached:
        return None
    return _parse_user_from_cache(cached)


class _HTTPBearer(FastAPIHTTPBearer):
    auto_error = True

    async def __call__(self, request: Request) -> UserSchema:  # type: ignore[override]
        # Base class declares Optional[HTTPAuthorizationCredentials]; we return
        # UserSchema intentionally. Safe because _HTTPBearer is only used as a
        # FastAPI dependency, never passed where HTTPBearer is expected directly.
        credentials: HTTPAuthorizationCredentials = await super().__call__(request)
        token = credentials.credentials
        user_data = await _lookup_token(token)
        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired authorization token.",
            )
        raw_id = user_data.get("id")
        if not isinstance(raw_id, int) or isinstance(raw_id, bool):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization token missing user identity.",
            )
        role_permissions = user_data.get("role_permissions", {})
        if not isinstance(role_permissions, dict):
            role_permissions = {}
        return UserSchema(id=raw_id, token=token, role_permissions=role_permissions)


_bearer_scheme = _HTTPBearer()


async def is_authenticated(request: Request) -> UserSchema:
    settings = get_settings()
    if settings.DEV_BYPASS:
        logger.warning(
            "DEV_BYPASS enabled: hardcoded admin user returned. Not for production."
        )
        return UserSchema(id=1, token="dev", role_permissions={"admin": True})
    return await _bearer_scheme(request)
