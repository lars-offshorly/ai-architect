"""Legacy generator schemas used by integration tests."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ModuleConfig(BaseModel):
    module_key: str
    enabled: bool
    config: dict[str, object] = Field(default_factory=dict)


class WorkspaceMeta(BaseModel):
    team_size: int
    industry_hint: str
    generated_at: str


class GenerationJSON(BaseModel):
    schema_version: Literal["1.0"]
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
    schema_version: Literal["1.0"]
    session_id: str
    bundle: str
    stores: StoreData


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
