from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EditPreviewRequestSchema(BaseModel):
    """Request body for POST /sessions/{id}/preview/edit."""

    current_preview: dict[str, Any] = Field(
        ...,
        description=(
            "The full AppPayloadResponseSchema output from a prior "
            "/preview or /preview/early call."
        ),
    )
    instruction: str = Field(
        ...,
        description=(
            "Natural-language edit instruction " "(e.g. 'remove the chat module')."
        ),
        min_length=1,
        max_length=500,
    )
