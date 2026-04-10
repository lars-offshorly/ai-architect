from __future__ import annotations

from core.exceptions import InvalidPayloadError
from core.logging import get_logger

logger = get_logger(__name__)


def validate_generation_json(data: dict[str, object], bundle_key: str) -> None:
    required = {"schema_version", "bundle_key", "modules", "config"}
    missing = required - data.keys()
    if missing:
        raise InvalidPayloadError(f"generation_json missing keys: {missing}")
    if data.get("bundle_key") != bundle_key:
        raise InvalidPayloadError(
            f"generation_json bundle_key mismatch: expected={bundle_key}"
        )
    modules = data.get("modules")
    if not isinstance(modules, list) or not modules:
        raise InvalidPayloadError("generation_json 'modules' must be a non-empty list")
    logger.info("generation_json validation passed for bundle=%s", bundle_key)


def validate_dummy_data_json(data: dict[str, object], bundle_key: str) -> None:
    required = {"bundle_key", "stores"}
    missing = required - data.keys()
    if missing:
        raise InvalidPayloadError(f"dummy_data_json missing keys: {missing}")
    if data.get("bundle_key") != bundle_key:
        raise InvalidPayloadError(
            f"dummy_data_json bundle_key mismatch: expected={bundle_key}"
        )
    stores = data.get("stores")
    if not isinstance(stores, dict):
        raise InvalidPayloadError("dummy_data_json 'stores' must be a dict")
    logger.info("dummy_data_json validation passed for bundle=%s", bundle_key)
