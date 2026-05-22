from __future__ import annotations

from pydantic import ValidationError

from agents.preview_generator.schemas import TenantProvisioningManifest
from core.exceptions import InvalidPayloadError
from core.logging import get_logger

logger = get_logger(__name__)


def validate_manifest(data: dict[str, object]) -> None:
    try:
        TenantProvisioningManifest.model_validate(data)
    except ValidationError as exc:
        raise InvalidPayloadError(str(exc)) from exc
    logger.info("manifest validation passed for session=%s", data.get("session_id"))
