from __future__ import annotations

from pydantic import BaseModel, Field


class PreviewJson(BaseModel):
    schema_version: str = "1.0"
    session_id: str
    bundle_key: str
    display_name: str
    modules: list[str] = Field(default_factory=list)
    stores: dict[str, list[dict[str, object]]] = Field(default_factory=dict)
    metadata: dict[str, object] = Field(default_factory=dict)
