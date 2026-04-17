"""relationship_mapper — load entity relationships from bundle_registry.yaml.

Load entity relationships from bundle_registry.yaml definitions.

Converts the explicit ``entity_relationships`` list declared under each bundle's
``metadata`` section in ``bundle_registry.yaml`` into typed ``EntityRelationship``
records that get embedded in ``generation_json["config"]["relationships"]``.

This replaces the previous token-suffix inference approach, which produced
incorrect relationships for indirect chains (e.g. leave_request → department).
Relationships are now correct by construction — defined once in the YAML and
loaded here without any inference logic.

Relationship types supported:
  has_many    — source contains many of target (e.g. department has_many employee)
  belongs_to  — source is owned by target    (e.g. employee belongs_to department)
  references  — loose association             (e.g. project references team_member)
  many_to_many — bidirectional plural link   (e.g. agent many_to_many ticket)
"""

from __future__ import annotations

from core.logging import get_logger
from domain.models.bundle_metadata import EntityDefinition, EntityRelationshipDefinition

from ..schemas import EntityRelationship

logger = get_logger(__name__)


def _resolve_display(
    key: str,
    entity_defs: dict[str, EntityDefinition],
) -> tuple[str, str]:
    """Return ``(label, plural)`` for an entity key.

    Falls back to a title-cased version of the key when it is absent from
    ``entity_defs``, using ``"<Label>s"`` as the synthetic plural.
    """
    if key in entity_defs:
        defn = entity_defs[key]
        return defn.label, defn.plural
    label = key.replace("_", " ").title()
    return label, label + "s"


def _build_label(
    src_label: str,
    tgt_label: str,
    tgt_plural: str,
    relation_type: str,
) -> str:
    """Build a human-readable label from resolved display strings."""
    if relation_type == "has_many":
        return f"{src_label} has many {tgt_plural}"
    if relation_type == "belongs_to":
        return f"{src_label} belongs to {tgt_label}"
    if relation_type == "many_to_many":
        return f"{src_label} and {tgt_plural} are many-to-many"
    return f"{src_label} references {tgt_label}"


def map_relationships(
    bundle_key: str,
    entity_relationships: list[EntityRelationshipDefinition],
    entity_definitions: dict[str, EntityDefinition],
) -> list[EntityRelationship]:
    """Convert explicit YAML relationship definitions into typed records.

    Args:
        bundle_key:           Render key of the bundle (e.g. ``"hr_hub"``).
                              Used for logging only.
        entity_relationships: Relationship entries parsed from
                              ``bundle_registry.yaml``
                              ``metadata.entity_relationships``.
        entity_definitions:   Entity label/plural map from
                              ``bundle_registry.yaml`` ``metadata.entity_definitions``.
                              Used to auto-generate labels when the YAML entry
                              omits the optional ``label`` field.

    Returns:
        One ``EntityRelationship`` per entry in ``entity_relationships``.
        Returns an empty list when ``entity_relationships`` is empty.
    """
    logger.debug(
        "map_relationships: bundle_key=%s relationships=%d",
        bundle_key,
        len(entity_relationships),
    )
    if not entity_relationships:
        return []

    result: list[EntityRelationship] = []
    for rel_def in entity_relationships:
        if rel_def.label:
            label = rel_def.label
        else:
            src_label, _ = _resolve_display(rel_def.source, entity_definitions)
            tgt_label, tgt_plural = _resolve_display(rel_def.target, entity_definitions)
            label = _build_label(src_label, tgt_label, tgt_plural, rel_def.type)

        result.append(
            EntityRelationship(
                source_entity=rel_def.source,
                target_entity=rel_def.target,
                relation_type=rel_def.type,
                label=label,
            )
        )
    return result
