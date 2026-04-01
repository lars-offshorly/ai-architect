from __future__ import annotations

from pydantic import ValidationError

from agents.app_generator.schemas import DummyDataJsonSchema, GenerationJsonSchema
from core.exceptions import InvalidPayloadError
from core.logging import get_logger

logger = get_logger(__name__)


def validate_generation_json(data: dict[str, object], bundle_key: str) -> None:
    """Validate *data* against :class:`GenerationJsonSchema`.

    Raises :class:`~core.exceptions.InvalidPayloadError` on any schema
    violation, including bundle-key mismatches and missing required fields.
    """
    if data.get("bundle_key") != bundle_key:
        raise InvalidPayloadError(
            f"generation_json bundle_key mismatch: expected={bundle_key!r}, "
            f"got={data.get('bundle_key')!r}"
        )
    try:
        GenerationJsonSchema.model_validate(data)
    except ValidationError as exc:
        raise InvalidPayloadError(
            f"generation_json failed schema validation: {exc}"
        ) from exc
    logger.info("generation_json validation passed for bundle=%s", bundle_key)


def validate_dummy_data_json(data: dict[str, object], bundle_key: str) -> None:
    """Validate *data* against :class:`DummyDataJsonSchema`.

    Raises :class:`~core.exceptions.InvalidPayloadError` on any schema
    violation, including missing ``stores`` or unrecognised bundle keys.
    """
    try:
        DummyDataJsonSchema.model_validate(data)
    except ValidationError as exc:
        raise InvalidPayloadError(
            f"dummy_data_json failed schema validation: {exc}"
        ) from exc
    logger.info("dummy_data_json validation passed for bundle=%s", bundle_key)
