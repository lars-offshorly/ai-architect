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
    v2_manifest: dict[str, object] | None = _UNSET,
    generation_json: dict[str, object] | None = _UNSET,
    dummy_data_json: dict[str, object] | None = _UNSET,
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
        generation_json=payload.generation_json if generation_json is _UNSET else generation_json,
        dummy_data_json=payload.dummy_data_json if dummy_data_json is _UNSET else dummy_data_json,
        preview_type=preview_type,
        warning=warning,
        v2_manifest=payload.v2_manifest if v2_manifest is _UNSET else v2_manifest,
    )
