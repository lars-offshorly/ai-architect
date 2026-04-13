"""config_encoder — encode preview configuration into the final JSON blueprint.

Transforms the structured preview config produced by the preview generator into
the provisioning JSON blueprint consumed by the backend.  This is a pure
transformation step: no I/O, no external calls.

Responsibility
--------------
- Accept a ``bundle_key`` and a raw config dict (preview-generator output).
- Validate required keys are present and types are correct.
- Emit a normalised ``generation_json``-compatible config dict ready for
  backend provisioning.

# TODO(CORE-AI-014): Implement full encoding logic for Configuration JSON
#   Encoding Engine. Replace the passthrough fallback with real transformation
#   once the preview-generator output schema is stabilised.
"""

from __future__ import annotations

from core.logging import get_logger

logger = get_logger(__name__)

# Known render keys — kept in sync with config_assembly and mock_builder.
_KNOWN_BUNDLE_KEYS: frozenset[str] = frozenset(
    {"hr_hub", "project_mgmt", "ticketing", "generic"}
)


def encode_config(
    bundle_key: str,
    preview_config: dict[str, object],
) -> dict[str, object]:
    """Encode preview configuration into the final JSON blueprint.

    Currently returns ``preview_config`` unchanged as a passthrough fallback
    until the full encoding logic is implemented (CORE-AI-014).

    Args:
        bundle_key:     Render key of the target bundle (e.g. ``"hr_hub"``).
        preview_config: Raw configuration dict emitted by the preview generator.

    Returns:
        A normalised config dict suitable for embedding in ``generation_json``.
        Returns an empty dict when ``preview_config`` is None or empty so that
        callers can safely proceed without crashing.

    Raises:
        ValueError: If ``bundle_key`` is an empty string.
    """
    # --- input validation -------------------------------------------------
    if not bundle_key or not bundle_key.strip():
        raise ValueError("bundle_key must be a non-empty string.")

    if preview_config is None:
        logger.warning(
            "encode_config received None preview_config for bundle_key=%s; "
            "returning empty dict.",
            bundle_key,
        )
        return {}

    if not isinstance(preview_config, dict):
        logger.warning(
            "encode_config expected a dict for bundle_key=%s but got %s; "
            "returning empty dict.",
            bundle_key,
            type(preview_config).__name__,
        )
        return {}

    if not preview_config:
        logger.warning(
            "encode_config received an empty preview_config for bundle_key=%s; "
            "returning empty dict.",
            bundle_key,
        )
        return {}

    if bundle_key not in _KNOWN_BUNDLE_KEYS:
        logger.warning(
            "encode_config called with unrecognised bundle_key=%r. "
            "Known keys: %s. Proceeding with passthrough.",
            bundle_key,
            sorted(_KNOWN_BUNDLE_KEYS),
        )

    # --- temporary passthrough (remove once CORE-AI-014 is implemented) ---
    # TODO(CORE-AI-014): Replace passthrough with real encoding logic.
    logger.warning(
        "encode_config is a passthrough stub (CORE-AI-014 not yet implemented). "
        "bundle_key=%s keys=%s",
        bundle_key,
        list(preview_config.keys()),
    )
    return dict(preview_config)
