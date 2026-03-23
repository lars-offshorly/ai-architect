from __future__ import annotations

from pydantic import BaseModel, Field


class AppPayloadResponseSchema(BaseModel):
    schema_version: str
    session_id: str
    bundle_key: str
    display_name: str
    modules: list[str] = Field(default_factory=list)
    generation_json: dict[str, object] = Field(default_factory=dict)
    dummy_data_json: dict[str, object] = Field(default_factory=dict)
