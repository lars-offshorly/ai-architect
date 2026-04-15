"""Dashboard generation HTTP client.

Posts a personalized template payload to the external dashboard service and
returns the response dict. All failures are handled gracefully — the caller
receives None and the preview pipeline continues with an empty widget list.
"""

from __future__ import annotations

import httpx

from core.logging import get_logger

from .auth import KnitAuthService

logger = get_logger(__name__)

_GENERATE_PATH = "/api/v1/dashboards/generate/"


class DashboardClient:
    """Sends dashboard generation requests to the Knit dashboard service.

    Failure modes (network error, timeout, 4xx/5xx) are caught and logged at
    WARNING level — never raised. This keeps dashboard enrichment optional:
    if the service is unavailable, ``dashboard_widgets`` stays as ``[]``.

    On a 401 response the token is invalidated and one retry is attempted
    before giving up.
    """

    def __init__(
        self,
        base_url: str,
        auth_service: KnitAuthService,
        timeout: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._auth = auth_service
        self._timeout = timeout

    def generate(self, payload: dict) -> dict | None:
        """POST payload to /api/v1/dashboards/generate/.

        Args:
            payload: Personalised dashboard template dict.

        Returns:
            Full JSON response dict on success (``success`` key is True),
            or None on any failure.
        """
        url = f"{self._base_url}{_GENERATE_PATH}"

        for attempt in range(2):  # up to 1 retry on 401
            token = self._auth.get_token()
            if not token:
                logger.warning("Dashboard client: no auth token available — skipping")
                return None

            try:
                response = httpx.post(
                    url,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    timeout=self._timeout,
                )
            except httpx.TimeoutException:
                logger.warning(
                    "Dashboard generate timed out after %.1fs", self._timeout
                )
                return None
            except httpx.RequestError as exc:
                logger.warning(
                    "Dashboard generate network error: %s", type(exc).__name__
                )
                return None

            if response.status_code == 401 and attempt == 0:
                logger.info(
                    "Dashboard client: 401 received — invalidating token and retrying"
                )
                self._auth.invalidate()
                continue

            if not response.is_success:
                logger.warning(
                    "Dashboard generate HTTP %s: %s",
                    response.status_code,
                    response.text[:300],
                )
                return None

            data: dict = response.json()
            if not data.get("success"):
                logger.warning(
                    "Dashboard generate returned success=false: %s",
                    str(data)[:300],
                )
                return None

            logger.info(
                "Dashboard generated: id=%s url=%s",
                data.get("dashboard", {}).get("id"),
                data.get("dashboard", {}).get("url"),
            )
            return data

        return None
