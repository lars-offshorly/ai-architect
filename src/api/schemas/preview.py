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
