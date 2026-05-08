from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AppPayloadResponseSchema(BaseModel):
    schema_version: str
    session_id: str
    bundle_key: str
    display_name: str
    modules: list[str] = Field(default_factory=list)
    generation_json: dict[str, object] = Field(default_factory=dict)
    dummy_data_json: dict[str, object] = Field(default_factory=dict)
    generation_schema: dict[str, object] = Field(default_factory=dict)
    sample_data: dict[str, object] = Field(default_factory=dict)
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
