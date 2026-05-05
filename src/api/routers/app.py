"""Router: final app generation and packaging endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from agents.app_generator.service import AppGeneratorService
from api.deps import (
    get_app_generator_service,
    get_bundle_catalog,
    get_session_repository,
)
from api.schemas.app_payload import AppPayloadResponseSchema
from api.schemas.request import GenerateAppRequest
from catalog.bundle_catalog import BundleCatalog
from core.exceptions import (
    InvalidPayloadError,
    PreviewGenerationError,
    SessionNotFoundError,
)
from core.logging import get_logger
from repositories.session_repository import SessionRepository

router = APIRouter(prefix="/sessions", tags=["app"])
logger = get_logger(__name__)


@router.post("/{session_id}/app", response_model=AppPayloadResponseSchema)
async def generate_app_payload(
    session_id: str,
    body: GenerateAppRequest,
    session_repo: Annotated[SessionRepository, Depends(get_session_repository)],
    app_generator: Annotated[AppGeneratorService, Depends(get_app_generator_service)],
    catalog: Annotated[BundleCatalog, Depends(get_bundle_catalog)],
) -> AppPayloadResponseSchema:
    """Assembles the final app payload for a confirmed session.

    Loads the static app.json from templates, validates it against the
    provided dummy_data, and packages the result into the AppPayload contract.
    """
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

    if not catalog.has_bundle(session.selected_bundle_key):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bundle not found: {session.selected_bundle_key}",
        )

    bundle = catalog.get(session.selected_bundle_key)
    display_name = bundle.display_name if bundle else session.selected_bundle_key

    # Use the session-stored bundle info + the client-provided dummy data
    try:
        payload = app_generator.assemble(
            session_id=session_id,
            bundle_key=session.selected_bundle_key,
            display_name=display_name,
            dummy_data=body.dummy_data_json,
            generation_data=body.generation_json,
        )
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
        schema_version=payload.schema_version,
        session_id=payload.session_id,
        bundle_key=payload.bundle_key,
        display_name=payload.display_name,
        modules=payload.modules,
        generation_json=payload.generation_json,
        dummy_data_json=payload.dummy_data_json,
        preview_type="confirmed",
    )
