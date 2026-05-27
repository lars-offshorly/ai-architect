from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field, field_validator

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


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

    @field_validator("instruction")
    @classmethod
    def _sanitize_instruction(cls, value: str) -> str:
        normalized = re.sub(r"\s+", " ", value).strip()
        if not normalized:
            raise ValueError("instruction cannot be empty")
        if _CONTROL_CHARS.search(normalized):
            raise ValueError("instruction contains control characters")
        return normalized
