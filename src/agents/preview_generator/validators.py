from __future__ import annotations

from core.exceptions import PreviewGenerationError
from core.logging import get_logger

logger = get_logger(__name__)

_REQUIRED_PREVIEW_KEYS: frozenset[str] = frozenset(
    {"schema_version", "bundle_key", "stores"}
)
_REQUIRED_DUMMY_KEYS: frozenset[str] = frozenset({"bundle_key", "stores"})


def validate_preview_json(data: dict[str, object], bundle_key: str) -> None:
    missing = _REQUIRED_PREVIEW_KEYS - data.keys()
    if missing:
        raise PreviewGenerationError(f"preview.json missing keys: {missing}")
    if data.get("bundle_key") != bundle_key:
        raise PreviewGenerationError(
            f"bundle_key mismatch: expected={bundle_key} got={data.get('bundle_key')}"
        )
    stores = data.get("stores")
    if not isinstance(stores, dict):
        raise PreviewGenerationError("preview.json 'stores' must be a dict")
    logger.info("Preview JSON validation passed for bundle=%s", bundle_key)


def validate_dummy_data(data: dict[str, object], bundle_key: str) -> None:
    missing = _REQUIRED_DUMMY_KEYS - data.keys()
    if missing:
        raise PreviewGenerationError(f"dummy_data.json missing keys: {missing}")
    stores = data.get("stores")
    if not isinstance(stores, dict):
        raise PreviewGenerationError("dummy_data.json 'stores' must be a dict")
    logger.info("Dummy data validation passed for bundle=%s", bundle_key)
