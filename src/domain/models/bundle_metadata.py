from __future__ import annotations

from pydantic import BaseModel, Field


class EntityDefinition(BaseModel):
    label: str
    plural: str


class EntityRelationshipDefinition(BaseModel):
    """A single relationship entry as declared in ``bundle_registry.yaml``."""

    source: str = Field(description="Source entity key, e.g. 'employee'.")
    target: str = Field(description="Target entity key, e.g. 'leave_request'.")
    type: str = Field(
        description="Relationship type: 'has_many', 'belongs_to', or 'references'."
    )
    label: str | None = Field(
        default=None, description="Optional human-readable override label."
    )


class BundleMetadata(BaseModel):
    bundle_key: str
    kpis: list[str] = Field(default_factory=list)
    workflows: list[str] = Field(default_factory=list)
    entity_definitions: dict[str, EntityDefinition] = Field(default_factory=dict)
    entity_relationships: list[EntityRelationshipDefinition] = Field(
        default_factory=list
    )
    onboarding_config_requirements: list[str] = Field(default_factory=list)
    coverage: list[str] = Field(default_factory=list)
    settings_configurations: list[str] = Field(default_factory=list)


__all__ = ["BundleMetadata", "EntityDefinition", "EntityRelationshipDefinition"]
