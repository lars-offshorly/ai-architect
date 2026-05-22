from __future__ import annotations

from typing import Any, Literal

from api.schemas.app_payload import AppPayloadResponseSchema
from domain.models.app_payload import AppPayload

_UNSET: Any = object()


def build_payload_response(
    payload: AppPayload,
    *,
    preview_type: Literal["confirmed", "early"] | None = None,
    warning: str | None = None,
    manifest: dict[str, object] | None = _UNSET,
) -> AppPayloadResponseSchema:
    """Assemble AppPayloadResponseSchema from an AppPayload.
    Keyword-only overrides let callers replace individual fields without
    repeating the fixed payload fields. Omitted overrides fall back to
    the corresponding field on payload.
    """
    return AppPayloadResponseSchema(
        schema_version=payload.schema_version,
        session_id=payload.session_id,
        bundle_key=payload.bundle_key,
        display_name=payload.display_name,
        modules=payload.modules,
        preview_type=preview_type,
        warning=warning,
        manifest=payload.manifest if manifest is _UNSET else manifest,
    )
