"""Request schema for the static mock payload endpoint."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class MockPayloadRequestSchema(BaseModel):
    """Request body for POST /mock/{bundle_key}."""

    session_id: str | None = None
    display_name: str | None = None
    manifest: dict[str, Any] | None = None
