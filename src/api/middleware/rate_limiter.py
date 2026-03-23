from __future__ import annotations

import asyncio
import time
from collections import deque

from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from core import get_settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: object) -> None:
        super().__init__(app)
        self._requests: dict[str, deque[float]] = {}
        self._lock = asyncio.Lock()

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        if request.url.path == "/health":
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        limit = max(1, int(get_settings().RATE_LIMIT_PER_MINUTE))
        allowed = await self._allow_request(client_ip, limit, 60.0)
        if not allowed:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded. Please try again later."},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        return response

    async def _allow_request(
        self,
        client_ip: str,
        limit: int,
        window_seconds: float,
    ) -> bool:
        now = time.monotonic()
        window_start = now - window_seconds

        async with self._lock:
            history = self._requests.setdefault(client_ip, deque())
            while history and history[0] <= window_start:
                history.popleft()
            if len(history) >= limit:
                return False
            history.append(now)
            return True
