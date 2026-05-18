"""config_assembly — helpers that shape the final ``generation_json`` config.

Currently contains a single live helper:

    relationship_mapper.map_relationships  Infer entity relationships
                                            from bundle entity definitions.

The earlier ``config_encoder`` / ``customization_merger`` / ``config_optimizer``
stubs (CORE-AI-012/014/016) were removed pending a decision on whether the
``generation_json.config`` concept survives the v2 manifest migration.
"""

from __future__ import annotations

from .relationship_mapper import map_relationships

__all__ = [
    "map_relationships",
]
