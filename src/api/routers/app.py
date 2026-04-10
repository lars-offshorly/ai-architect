"""Router: final app generation and packaging endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from api.deps import get_app_generator_service, get_session_repository
from api.schemas.app_payload import AppPayloadResponseSchema
from api.schemas.request import GenerateAppRequest
from core.exceptions import SessionNotFoundError
from core.logging import get_logger
from repositories.session_repository import SessionRepository
from agents.app_generator.service import AppGeneratorService

router = APIRouter(prefix="/sessions", tags=["app"])
logger = get_logger(__name__)


@router.post("/{session_id}/app", response_model=AppPayloadResponseSchema)
async def generate_app_payload(
    session_id: str,
    body: GenerateAppRequest,
    session_repo: Annotated[SessionRepository, Depends(get_session_repository)],
    app_generator: Annotated[AppGeneratorService, Depends(get_app_generator_service)],
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

    # Use the session-stored bundle info + the client-provided dummy data
    payload = app_generator.assemble(
        session_id=session_id,
        bundle_key=session.selected_bundle_key,
        display_name=session.selected_bundle_key,  # For now, use the key as display name
        dummy_data=body.dummy_data_json,
    )

    return AppPayloadResponseSchema(
        schema_version=payload.schema_version,
        session_id=payload.session_id,
        bundle_key=payload.bundle_key,
        display_name=payload.display_name,
        modules=payload.modules,
        generation_json=payload.generation_json,
        dummy_data_json=payload.dummy_data_json,
    )
