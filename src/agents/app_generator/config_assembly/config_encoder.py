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
"""

from __future__ import annotations

from core.logging import get_logger

logger = get_logger(__name__)

# Known render keys — kept in sync with config_assembly and mock_builder.
_KNOWN_BUNDLE_KEYS: frozenset[str] = frozenset(
    {"hr_hub", "project_mgmt", "ticketing", "generic"}
)

# Per-bundle field spec: (key_name, expected_type, default_value).
# Only list[str] fields and kpi_definitions are normalised; other types pass
# through after the type check.
_BUNDLE_REQUIRED_KEYS: dict[str, list[tuple[str, type, object]]] = {
    "hr_hub": [
        ("ticket_categories",   list, []),
        ("default_statuses",    list, []),
        ("default_priorities",  list, []),
        ("queue_names",         list, []),
        ("kpi_definitions",     list, []),
        ("permission_services", list, []),
        ("landing_pages",       list, []),
    ],
    "project_mgmt": [
        ("task_statuses",       list, []),
        ("task_priorities",     list, []),
        ("milestone_statuses",  list, []),
        ("kpi_definitions",     list, []),
        ("permission_services", list, []),
        ("landing_pages",       list, []),
    ],
    "ticketing": [
        ("work_order_statuses",   list, []),
        ("work_order_priorities", list, []),
        ("service_types",         list, []),
        ("kpi_definitions",       list, []),
        ("permission_services",   list, []),
        ("landing_pages",         list, []),
    ],
    "generic": [
        ("ticket_statuses",     list, []),
        ("ticket_priorities",   list, []),
        ("kpi_definitions",     list, []),
        ("permission_services", list, []),
        ("landing_pages",       list, []),
    ],
}

# Keys whose list items are plain strings and should be deduplicated/stripped.
_STR_LIST_KEYS: frozenset[str] = frozenset(
    {
        "ticket_categories",
        "default_statuses",
        "default_priorities",
        "queue_names",
        "task_statuses",
        "task_priorities",
        "milestone_statuses",
        "work_order_statuses",
        "work_order_priorities",
        "service_types",
        "ticket_statuses",
        "ticket_priorities",
        "permission_services",
    }
)


def _normalise_str_list(values: list) -> list[str]:
    """Deduplicate and strip a list of strings, preserving first-seen order."""
    seen: set[str] = set()
    result: list[str] = []
    for item in values:
        if not isinstance(item, str):
            continue
        cleaned = item.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
    return result


def _normalise_kpi_definitions(items: list, bundle_key: str) -> list[dict]:
    """Filter kpi_definitions to well-formed items that contain key, label, and unit."""
    result: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            logger.warning(
                "encode_config dropping non-dict kpi_definition for bundle_key=%s: %r",
                bundle_key,
                item,
            )
            continue
        missing = [f for f in ("key", "label", "unit") if not item.get(f)]
        if missing:
            logger.warning(
                "encode_config dropping kpi_definition missing fields %s "
                "for bundle_key=%s: %r",
                missing,
                bundle_key,
                item,
            )
            continue
        result.append(item)
    return result


def encode_config(
    bundle_key: str,
    preview_config: dict[str, object],
) -> dict[str, object]:
    """Encode preview configuration into the final JSON blueprint.

    Validates required bundle-specific keys, normalises list values (deduplication,
    whitespace stripping), filters malformed ``kpi_definitions`` items, and fills
    missing optional fields with empty-list defaults.  Extra keys not declared in
    the bundle spec (e.g. ``relationships`` injected upstream) are preserved as-is.

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
        return dict(preview_config)

    # --- encoding ---------------------------------------------------------
    # Start with a shallow copy; extra keys not in the spec are preserved.
    encoded: dict[str, object] = dict(preview_config)
    spec = _BUNDLE_REQUIRED_KEYS[bundle_key]

    for key, expected_type, default in spec:
        value = encoded.get(key)

        if value is None:
            logger.warning(
                "encode_config: required key %r missing for bundle_key=%s; "
                "inserting default %r.",
                key,
                bundle_key,
                default,
            )
            encoded[key] = list(default)  # type: ignore[arg-type]
            continue

        if not isinstance(value, expected_type):
            logger.warning(
                "encode_config: key %r expected %s but got %s for bundle_key=%s; "
                "replacing with default.",
                key,
                expected_type.__name__,
                type(value).__name__,
                bundle_key,
            )
            encoded[key] = list(default)  # type: ignore[arg-type]
            continue

        # Normalise list values
        if key == "kpi_definitions":
            encoded[key] = _normalise_kpi_definitions(
                value,  # type: ignore[arg-type]
                bundle_key,
            )
        elif key in _STR_LIST_KEYS:
            encoded[key] = _normalise_str_list(value)  # type: ignore[arg-type]

    return encoded
