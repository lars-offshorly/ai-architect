"""Knit platform authentication service.

Obtains a Bearer token from the Knit auth endpoint and caches it in memory
with a configurable TTL. Thread-safe via a threading.Lock.

Credentials are read exclusively from environment-backed Settings — never
hardcoded. The token value is never logged.
"""

from __future__ import annotations

import threading
import time
from typing import Optional

import httpx

from core.logging import get_logger

logger = get_logger(__name__)


class KnitAuthService:
    """Fetches and caches a Knit platform Bearer token.

    Usage:
        auth = KnitAuthService(auth_url, email, password, ttl_seconds=2700)
        token = auth.get_token()   # cached until TTL expires

    The token is refreshed lazily on the next ``get_token()`` call after
    expiry. If the refresh fails, the previous token is returned (if any)
    so callers can still attempt the request; a warning is logged.
    """

    def __init__(
        self,
        auth_url: str,
        email: str,
        password: str,
        ttl_seconds: int = 2700,
        timeout: float = 10.0,
    ) -> None:
        if not auth_url:
            raise ValueError("KNIT_AUTH_URL must be set")
        if not email or not password:
            raise ValueError("KNIT_EMAIL and KNIT_PASSWORD must be set")

        self._auth_url = auth_url
        self._email = email
        self._password = password
        self._ttl = ttl_seconds
        self._timeout = timeout

        self._token: Optional[str] = None
        self._expires_at: float = 0.0
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_token(self) -> Optional[str]:
        """Return a valid Bearer token, refreshing if expired.

        Returns None only when no token has ever been fetched successfully
        (i.e. the very first call fails). Subsequent failures after a prior
        success return the stale token with a warning rather than None.
        """
        with self._lock:
            if self._is_valid():
                return self._token
            return self._refresh()

    def invalidate(self) -> None:
        """Force the next ``get_token()`` call to re-authenticate."""
        with self._lock:
            self._expires_at = 0.0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_valid(self) -> bool:
        return self._token is not None and time.monotonic() < self._expires_at

    def _refresh(self) -> Optional[str]:
        """POST credentials, parse token, update cache. Caller holds lock."""
        logger.info("Refreshing Knit auth token from %s", self._auth_url)
        try:
            response = httpx.post(
                self._auth_url,
                json={"email": self._email, "password": self._password},
                timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "Knit auth HTTP error: status=%s — %s",
                exc.response.status_code,
                exc.response.text[:200],
            )
            return self._token  # return stale token if available
        except httpx.RequestError as exc:
            logger.warning("Knit auth request failed: %s", type(exc).__name__)
            return self._token

        token = self._parse_token(response.json())
        if token is None:
            logger.warning(
                "Knit auth response did not contain a recognised token field"
            )
            return self._token

        self._token = token
        self._expires_at = time.monotonic() + self._ttl
        logger.info("Knit auth token refreshed — valid for %ds", self._ttl)
        return self._token

    @staticmethod
    def _parse_token(data: dict) -> Optional[str]:
        """Extract the token string from the login response.

        Tries common field names in priority order:
          token → access_token → data.token → data.access_token → key
        """
        if not isinstance(data, dict):
            return None
        for key in ("token", "access_token", "key"):
            if isinstance(data.get(key), str) and data[key]:
                return data[key]
        nested = data.get("data")
        if isinstance(nested, dict):
            for key in ("token", "access_token", "key"):
                if isinstance(nested.get(key), str) and nested[key]:
                    return nested[key]
        return None
