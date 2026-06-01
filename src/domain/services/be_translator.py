from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Literal, Protocol

import httpx

from core.logging import get_logger

logger = get_logger(__name__)

BEOperation = Literal["create", "edit", "remove", "rename"]


class BETranslatorClient(Protocol):
    async def translate_preview(
        self,
        *,
        request_id: str,
        document_id: str,
        revision: int,
        operation: BEOperation,
        preview_json: dict[str, Any],
    ) -> dict[str, Any]: ...


class MockBETranslatorClient:
    def __init__(self, delay_ms: int = 0) -> None:
        self._delay_ms = delay_ms

    async def translate_preview(
        self,
        *,
        request_id: str,
        document_id: str,
        revision: int,
        operation: BEOperation,
        preview_json: dict[str, Any],
    ) -> dict[str, Any]:
        if self._delay_ms > 0:
            await asyncio.sleep(self._delay_ms / 1000)
        return {
            "requestId": request_id,
            "documentId": document_id,
            "revision": revision,
            "operation": operation,
            "status": "accepted",
            "translatedPreview": preview_json,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


class HttpBETranslatorClient:
    def __init__(self, url: str, timeout_ms: int) -> None:
        self._url = url
        self._timeout = timeout_ms / 1000

    async def translate_preview(
        self,
        *,
        request_id: str,
        document_id: str,
        revision: int,
        operation: BEOperation,
        preview_json: dict[str, Any],
    ) -> dict[str, Any]:
        payload = {
            "requestId": request_id,
            "documentId": document_id,
            "revision": revision,
            "operation": operation,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "idempotencyKey": f"{document_id}:{revision}",
            "previewJson": preview_json,
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(self._url, json=payload)
            response.raise_for_status()
            data = response.json()
            return dict(data) if isinstance(data, dict) else {}
