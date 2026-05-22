"""Minimal app generator schemas used by runtime helpers."""

from __future__ import annotations

from pydantic import BaseModel, Field


class EntityRelationship(BaseModel):
    """Directed relationship between two bundle entities."""

    source_entity: str = Field(description="Source entity key.")
    target_entity: str = Field(description="Target entity key.")
    relation_type: str = Field(description="Relationship type.")
    label: str | None = Field(default=None, description="Human-readable label.")
