from __future__ import annotations

from pydantic import BaseModel, Field


class TemplateMetadata(BaseModel):
    bundle: str
    industry_hint: str
    modules: list[str] = Field(default_factory=list)
    required_slots: list[str] = Field(default_factory=list)
    version: str
    content: str


class RetrievedTemplate(BaseModel):
    metadata: TemplateMetadata
    content: str
    score: float
    source: str


class ModuleConfig(BaseModel):
    module_key: str
    enabled: bool = True
    config: dict[str, object] = Field(default_factory=dict)


class WorkspaceMeta(BaseModel):
    team_size: int | None = None
    industry_hint: str | None = None
    generated_at: str


class GenerationJSON(BaseModel):
    schema_version: str
    session_id: str
    bundle: str
    entity_type: str
    modules: list[ModuleConfig] = Field(default_factory=list)
    workspace_meta: WorkspaceMeta


class StoreData(BaseModel):
    tickets: list[dict[str, object]] = Field(default_factory=list)
    queues: list[dict[str, object]] = Field(default_factory=list)
    kpis: list[dict[str, object]] = Field(default_factory=list)
    dashboard_widgets: list[dict[str, object]] = Field(default_factory=list)


class DummyDataJSON(BaseModel):
    schema_version: str
    session_id: str
    bundle: str
    stores: StoreData
