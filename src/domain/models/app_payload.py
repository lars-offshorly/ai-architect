from __future__ import annotations

from pydantic import BaseModel, Field


class AppPayload(BaseModel):
    schema_version: str = "2.0"
    session_id: str
    bundle_key: str
    display_name: str
    modules: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)
    manifest: dict[str, object]
