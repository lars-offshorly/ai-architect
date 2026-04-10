"""relationship_mapper — infer entity relationships from bundle entity definitions.

Pure functions, no I/O.  Input comes from BundleCatalog via
``bundle.metadata.entity_definitions``; output is embedded into
``generation_json["config"]["relationships"]`` during assembly.

Relationship type inference rules (applied per ordered pair):
  - If the *target* entity key ends with a "child" suffix token
    (request, task, order, record, event, log): source → has_many target
  - If the *source* entity key ends with a "child" suffix token:
    source → belongs_to target
  - Otherwise: source → references target

These rules cover the common HR / ticketing / project patterns present in
``bundle_registry.yaml`` without requiring explicit relationship data in the YAML.
"""

from __future__ import annotations

import itertools

from core.logging import get_logger
from domain.models.bundle_metadata import EntityDefinition

from ..schemas import EntityRelationship

logger = get_logger(__name__)

# Token suffixes that indicate a "child / subordinate" entity.
_CHILD_TOKENS: frozenset[str] = frozenset(
    {"request", "task", "order", "record", "event", "log"}
)


def _last_token(entity_key: str) -> str:
    """Return the final underscore-separated token of an entity key."""
    parts = entity_key.rsplit("_", maxsplit=1)
    return parts[-1]


def _infer_relation_type(source_key: str, target_key: str) -> str:
    """Return the relation type for the directed edge source → target."""
    if _last_token(target_key) in _CHILD_TOKENS:
        return "has_many"
    if _last_token(source_key) in _CHILD_TOKENS:
        return "belongs_to"
    return "references"


def _make_label(
    source_key: str,
    target_key: str,
    relation_type: str,
    entity_defs: dict[str, EntityDefinition],
) -> str:
    """Build a human-readable label for a relationship edge."""
    src_label = (
        entity_defs[source_key].label
        if source_key in entity_defs
        else source_key.replace("_", " ").title()
    )
    tgt_label = (
        entity_defs[target_key].label
        if target_key in entity_defs
        else target_key.replace("_", " ").title()
    )
    tgt_plural = (
        entity_defs[target_key].plural
        if target_key in entity_defs
        else tgt_label + "s"
    )

    if relation_type == "has_many":
        return f"{src_label} has many {tgt_plural}"
    if relation_type == "belongs_to":
        return f"{src_label} belongs to {tgt_label}"
    return f"{src_label} references {tgt_label}"


def map_relationships(
    bundle_key: str,
    entity_definitions: dict[str, EntityDefinition],
) -> list[EntityRelationship]:
    """Produce typed relationship records from a bundle's entity definitions.

    Args:
        bundle_key:         Render key of the bundle (e.g. ``"hr_hub"``).
                            Reserved for future bundle-specific overrides and
                            logging; not used in the current inference logic.
        entity_definitions: Mapping of entity key → EntityDefinition sourced
                            from ``BundleCatalog.get(bundle_key).metadata``.

    Returns:
        One ``EntityRelationship`` for each ordered pair of distinct entity
        keys.  Returns an empty list when fewer than two entities are defined.
    """
    keys = list(entity_definitions.keys())
    logger.debug("map_relationships: bundle_key=%s entities=%s", bundle_key, keys)
    if len(keys) < 2:
        return []

    relationships: list[EntityRelationship] = []
    for source_key, target_key in itertools.permutations(keys, 2):
        relation_type = _infer_relation_type(source_key, target_key)
        label = _make_label(source_key, target_key, relation_type, entity_definitions)
        relationships.append(
            EntityRelationship(
                source_entity=source_key,
                target_entity=target_key,
                relation_type=relation_type,
                label=label,
            )
        )
    return relationships
