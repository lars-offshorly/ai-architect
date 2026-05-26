from __future__ import annotations

from pydantic import ValidationError

from agents.preview_generator.schemas import TenantProvisioningManifest
from core.exceptions import InvalidPayloadError
from core.logging import get_logger

logger = get_logger(__name__)


def format_manifest_validation_errors(exc: ValidationError) -> list[dict[str, str]]:
    details: list[dict[str, str]] = []
    for err in exc.errors():
        loc = ".".join(str(part) for part in err.get("loc", ()))
        details.append(
            {
                "path": loc or "manifest",
                "message": err.get("msg", "Invalid value"),
                "type": err.get("type", "validation_error"),
            }
        )
    return details


def validate_manifest_model(data: dict[str, object]) -> TenantProvisioningManifest:
    return TenantProvisioningManifest.model_validate(data)


def validate_manifest(data: dict[str, object]) -> None:
    try:
        validate_manifest_model(data)
    except ValidationError as exc:
        details = format_manifest_validation_errors(exc)
        raise InvalidPayloadError(str(details)) from exc
    logger.info("manifest validation passed for session=%s", data.get("session_id"))
