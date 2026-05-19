from __future__ import annotations

from pydantic import ValidationError

from agents.preview_generator.schemas import AppPayloadV2
from core.exceptions import InvalidPayloadError
from core.logging import get_logger

logger = get_logger(__name__)


def validate_generation_json(
    data: dict[str, object],
    bundle_key: str,
    compatible_bundle_keys: set[str] | None = None,
) -> None:
    required = {"schema_version", "bundle_key", "modules", "config"}
    missing = required - data.keys()
    if missing:
        raise InvalidPayloadError(f"generation_json missing keys: {missing}")
    actual_bundle_key = data.get("bundle_key")
    if actual_bundle_key != bundle_key:
        compatible_keys = compatible_bundle_keys or set()
        if (
            not isinstance(actual_bundle_key, str)
            or actual_bundle_key not in compatible_keys
        ):
            expected = sorted({bundle_key, *compatible_keys})
            raise InvalidPayloadError(
                "generation_json bundle_key mismatch: " f"expected one of={expected}"
            )
    modules = data.get("modules")
    if not isinstance(modules, list) or not modules:
        raise InvalidPayloadError("generation_json 'modules' must be a non-empty list")
    logger.info("generation_json validation passed for bundle=%s", bundle_key)


def validate_dummy_data_json(
    data: dict[str, object],
    bundle_key: str,
    compatible_bundle_keys: set[str] | None = None,
) -> None:
    required = {"bundle_key", "stores"}
    missing = required - data.keys()
    if missing:
        raise InvalidPayloadError(f"dummy_data_json missing keys: {missing}")
    actual_bundle_key = data.get("bundle_key")
    if actual_bundle_key != bundle_key:
        compatible_keys = compatible_bundle_keys or set()
        if (
            not isinstance(actual_bundle_key, str)
            or actual_bundle_key not in compatible_keys
        ):
            expected = sorted({bundle_key, *compatible_keys})
            raise InvalidPayloadError(
                "dummy_data_json bundle_key mismatch: " f"expected one of={expected}"
            )
    stores = data.get("stores")
    if not isinstance(stores, dict):
        raise InvalidPayloadError("dummy_data_json 'stores' must be a dict")
    logger.info("dummy_data_json validation passed for bundle=%s", bundle_key)


def validate_v2_manifest(data: dict[str, object]) -> None:
    try:
        AppPayloadV2.model_validate(data)
    except ValidationError as exc:
        raise InvalidPayloadError(str(exc)) from exc
    logger.info("v2 manifest validation passed for session=%s", data.get("session_id"))
