from __future__ import annotations

from pydantic import BaseModel, Field


class EntityDefinition(BaseModel):
    label: str
    plural: str


class BundleMetadata(BaseModel):
    bundle_key: str
    kpis: list[str] = Field(default_factory=list)
    workflows: list[str] = Field(default_factory=list)
    entity_definitions: dict[str, EntityDefinition] = Field(default_factory=dict)
    onboarding_config_requirements: list[str] = Field(default_factory=list)
    coverage: list[str] = Field(default_factory=list)
    settings_configurations: list[str] = Field(default_factory=list)


__all__ = ["BundleMetadata", "EntityDefinition"]
