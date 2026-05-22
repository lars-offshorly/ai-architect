"""Router: final app generation and packaging endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from agents.app_generator.validators import validate_manifest
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
from domain.services.registry_facade import RegistryFacade
from repositories.session_repository import SessionRepository

router = APIRouter(prefix="/sessions", tags=["app"])
logger = get_logger(__name__)


@router.post("/{session_id}/app", response_model=AppPayloadResponseSchema)
async def generate_app_payload(
    session_id: str,
    body: GenerateAppRequest,
    session_repo: Annotated[SessionRepository, Depends(get_session_repository)],
    registry_facade: Annotated[RegistryFacade, Depends(get_registry_facade)],
) -> AppPayloadResponseSchema:
    """Validate and return the manifest for a confirmed session."""
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

    try:
        validate_manifest(body.manifest)
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

    return AppPayloadResponseSchema(
        schema_version="2.0",
        session_id=session_id,
        bundle_key=session.selected_bundle_key,
        display_name=display_name,
        modules=[],
        preview_type="confirmed",
        manifest=body.manifest,
    )
