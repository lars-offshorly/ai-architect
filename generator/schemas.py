from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


TemplateSource = Literal["fetch", "search", "fallback"]


class TemplateMetadata(BaseModel):
    bundle: str
    industry_hint: str
    modules: list[str]
    required_slots: list[str]
    version: str
    content: str


class ModuleConfig(BaseModel):
    module_key: str
    enabled: bool = True
    config: dict[str, object] = Field(default_factory=dict)


class WorkspaceMeta(BaseModel):
    team_size: int | None = None
    industry_hint: str | None = None
    generated_at: str

    @field_validator("generated_at")
    @classmethod
    def validate_generated_at(cls, value: str) -> str:
        normalized_value = value.replace("Z", "+00:00")
        datetime.fromisoformat(normalized_value)
        return value


class GenerationJSON(BaseModel):
    schema_version: str
    session_id: str
    bundle: str
    entity_type: str
    modules: list[ModuleConfig]
    workspace_meta: WorkspaceMeta


class StoreData(BaseModel):
    tickets: list[dict[str, object]] = Field(default_factory=list)
    queues: list[dict[str, object]] = Field(default_factory=list)
    kpis: list[dict[str, object]] = Field(default_factory=list)
    dashboard_widgets: list[dict[str, object]] = Field(default_factory=list)
    tasks: list[dict[str, object]] = Field(default_factory=list)
    milestones: list[dict[str, object]] = Field(default_factory=list)
    assets: list[dict[str, object]] = Field(default_factory=list)
    maintenance: list[dict[str, object]] = Field(default_factory=list)


class DummyDataJSON(BaseModel):
    schema_version: str
    session_id: str
    bundle: str
    stores: StoreData


class RetrievedTemplate(BaseModel):
    metadata: TemplateMetadata
    content: str
    score: float = 0.0
    source: TemplateSource
