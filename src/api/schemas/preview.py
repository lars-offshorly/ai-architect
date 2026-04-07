from __future__ import annotations

from pydantic import BaseModel, Field


class PreviewStoreSchema(BaseModel):
    records: list[dict[str, object]] = Field(default_factory=list)


class PreviewResponseSchema(BaseModel):
    schema_version: str
    session_id: str
    bundle_key: str
    display_name: str
    modules: list[str] = Field(default_factory=list)
    stores: dict[str, list[dict[str, object]]] = Field(default_factory=dict)


class EditRequestSchema(BaseModel):
    instruction: str


class EditPreviewRequestSchema(BaseModel):
    """Request body for POST /sessions/{id}/preview/edit."""

    current_preview: dict[str, object] = Field(
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
