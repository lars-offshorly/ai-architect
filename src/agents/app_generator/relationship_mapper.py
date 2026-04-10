"""Backward-compatibility shim — re-exports from config_assembly.relationship_mapper.

The canonical location for this module is now:
    src/agents/app_generator/config_assembly/relationship_mapper.py

This file exists only so that any pre-existing import of the form
    from agents.app_generator.relationship_mapper import map_relationships
continues to work without modification.
"""

from __future__ import annotations

from .config_assembly.relationship_mapper import (  # noqa: F401
    map_relationships,
    _CHILD_TOKENS,
    _infer_relation_type,
    _last_token,
    _make_label,
)

__all__ = ["map_relationships"]
