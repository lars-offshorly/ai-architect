"""Router: final app generation and packaging endpoint."""

from __future__ import annotations

import json
import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError

from agents.tenant_provisioning.validators import (
    format_manifest_validation_errors,
    validate_manifest_model,
)
from api.deps import (
    get_registry_facade,
    get_session_repository,
)
from api.schemas.app_payload import AppPayloadResponseSchema
from api.schemas.request import GenerateAppRequest
from core.exceptions import (
    InvalidPayloadError,
    PreviewGenerationError,
    SessionNotFoundError,
)
from core.logging import get_logger
from core.metrics import metrics
from domain.services.registry_facade import RegistryFacade
from repositories.session_repository import SessionRepository

router = APIRouter(prefix="/sessions", tags=["app"])
logger = get_logger(__name__)


def _json_size_bytes(payload: object) -> int:
    return len(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )


@router.post("/{session_id}/app", response_model=AppPayloadResponseSchema)
async def generate_app_payload(
    session_id: str,
    body: GenerateAppRequest,
    session_repo: Annotated[SessionRepository, Depends(get_session_repository)],
    registry_facade: Annotated[RegistryFacade, Depends(get_registry_facade)],
) -> AppPayloadResponseSchema:
    """Validate and return the manifest for a confirmed session."""
    start = time.perf_counter()
    try:
        session = session_repo.get(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc

    if not session.confirmed or not session.selected_bundle_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session bundle must be confirmed before generating final app.",
        )

    if not registry_facade.has_bundle(session.selected_bundle_key):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bundle not found: {session.selected_bundle_key}",
        )

    display_name = session.selected_bundle_key
    from core.config import get_settings

    settings = get_settings()
    manifest_bytes = _json_size_bytes(body.manifest)
    if manifest_bytes > settings.MAX_APP_MANIFEST_BYTES:
        metrics.inc("app.rejected.payload_too_large")
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"manifest payload too large: {manifest_bytes} bytes "
                f"(max {settings.MAX_APP_MANIFEST_BYTES})"
            ),
        )

    try:
        validate_manifest_model(body.manifest)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "manifest_validation_error",
                "errors": format_manifest_validation_errors(exc),
            },
        ) from exc
    except InvalidPayloadError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except PreviewGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    response = AppPayloadResponseSchema(
        schema_version="2.0",
        session_id=session_id,
        bundle_key=session.selected_bundle_key,
        display_name=display_name,
        modules=[],
        preview_type="confirmed",
        manifest=body.manifest,
    )
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    metrics.inc("app.requests.total")
    if elapsed_ms >= 500:
        metrics.inc("app.latency.ge_500ms")
    logger.info(
        "app_event session=%s manifest_bytes=%s elapsed_ms=%s",
        session_id,
        manifest_bytes,
        elapsed_ms,
    )
    return response
