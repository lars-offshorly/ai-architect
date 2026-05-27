from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AppPayloadResponseSchema(BaseModel):
    schema_version: str
    session_id: str
    bundle_key: str
    display_name: str
    modules: list[str] = Field(default_factory=list)
    preview_type: Literal["confirmed", "early"] | None = Field(
        default=None,
        description=(
            "Discriminator for preview/app payloads. "
            "'confirmed' = derived from a confirmed bundle selection. "
            "'early' = generated before bundle confirmation."
        ),
    )
    warning: str | None = Field(
        default=None,
        description=(
            "Present when the preview was generated without full bundle confirmation. "
            "Indicates the output may contain generic or incomplete data."
        ),
    )
    manifest: dict[str, object] = Field(
        ...,
        description=(
            "v2 tenant-provisioning manifest (schema_version 2.0). "
            "Primary and only payload contract."
        ),
    )
