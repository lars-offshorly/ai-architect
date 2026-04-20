"""customization_merger — merge workspace customisation data into the base config.

Applies user- or session-supplied customisation (company name, team names,
custom labels, etc.) on top of the bundle base config produced by the encoding
step.  The merge is non-destructive: keys present in ``customization`` override
the corresponding keys in ``base_config``, while all other base keys are
preserved unchanged.

Responsibility
--------------
- Accept a base config dict and a customisation dict.
- Deep-merge customisation values into the base config.
- Return the merged config without mutating either input.
"""

from __future__ import annotations

from core.logging import get_logger

logger = get_logger(__name__)


def _deep_merge(
    base: dict[str, object],
    override: dict[str, object],
) -> dict[str, object]:
    """Recursively merge *override* into *base* without mutating either.

    Merge rules:
    - Nested dicts: recurse.
    - Lists and scalars: override value wins (replace, not union).
    - Keys absent in *override* are preserved from *base* unchanged.
    """
    result: dict[str, object] = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(
                result[key],  # type: ignore[arg-type]
                value,
            )
        else:
            result[key] = value
    return result


def extract_customization(
    dummy_data: dict[str, object],
    bundle_key: str,
) -> dict[str, object]:
    """Build a partial config override dict from *dummy_data* for *bundle_key*.

    Extracts workspace-specific values from the dummy data stores and maps
    them to the corresponding base config keys.  Only non-empty values are
    included — callers receive ``{}`` when nothing can be extracted.

    Current extraction mappings:

    +--------------+----------------------------+-------------------+
    | bundle_key   | dummy_data source          | config key        |
    +==============+============================+===================+
    | hr_hub       | stores.queues[].name       | queue_names       |
    +--------------+----------------------------+-------------------+

    Other bundles produce an empty dict until mappings are defined.
    """
    customization: dict[str, object] = {}

    if bundle_key == "hr_hub":
        stores = dummy_data.get("stores")
        if not isinstance(stores, dict):
            return customization

        queues = stores.get("queues")
        if not isinstance(queues, list):
            return customization

        names = [
            q["name"]
            for q in queues
            if isinstance(q, dict) and isinstance(q.get("name"), str) and q["name"].strip()
        ]
        if names:
            customization["queue_names"] = names
            logger.debug(
                "extract_customization: extracted %d queue_names for bundle_key=%s",
                len(names),
                bundle_key,
            )

    return customization


def merge_customization(
    base_config: dict[str, object],
    customization: dict[str, object],
) -> dict[str, object]:
    """Merge customisation data into the base bundle config.

    Args:
        base_config:    The assembled base config dict (output of
                        ``encode_config`` or loaded from the template).
        customization:  Workspace-specific overrides extracted from the
                        onboarding conversation (slots, company name, etc.).

    Returns:
        A new dict with customisation values applied over the base config.
        Neither input dict is mutated.  When *customization* is empty the
        return value is a shallow copy of *base_config*.
    """
    if not customization:
        return dict(base_config)
    return _deep_merge(base_config, customization)
