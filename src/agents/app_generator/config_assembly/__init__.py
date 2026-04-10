"""config_assembly — pipeline for producing the final generation_json config.

Sub-modules
-----------
relationship_mapper   Infer entity relationships from bundle entity definitions.
config_encoder        Encode preview configuration into the final JSON blueprint.
customization_merger  Merge workspace customization data into the base config.
config_optimizer      Remove redundancies and optimise the assembled JSON structure.
"""

from __future__ import annotations

from .config_encoder import encode_config
from .config_optimizer import optimize_config
from .customization_merger import merge_customization
from .relationship_mapper import map_relationships

__all__ = [
    "map_relationships",
    "encode_config",
    "merge_customization",
    "optimize_config",
]
