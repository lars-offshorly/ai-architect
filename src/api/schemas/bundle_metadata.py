from __future__ import annotations

from pydantic import BaseModel, Field  # noqa: I001

from domain.models.bundle_metadata import (
    BundleMetadata,
    EntityDefinition,
    EntityRelationshipDefinition,
)


class BundleMetadataResponseSchema(BaseModel):
    """HTTP response wrapper for GET /bundles/{bundle_key}/metadata.

    Mirrors :class:`domain.models.bundle_metadata.BundleMetadata` so that
    HTTP-contract changes can evolve independently of the domain model.
    """

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

    @classmethod
    def from_domain(cls, model: BundleMetadata) -> BundleMetadataResponseSchema:
        return cls.model_validate(model.model_dump())
