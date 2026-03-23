from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from api.deps import (
    get_conversation_repository,
    get_preview_flow,
    get_session_repository,
)
from api.schemas.app_payload import AppPayloadResponseSchema
from core.exceptions import BundleNotFoundError, SessionNotFoundError, TemplateLoadError
from core.logging import get_logger
from domain.models.extracted_info import ExtractedInfo
from orchestrators.preview_flow import PreviewFlow
from repositories.conversation_repository import ConversationRepository
from repositories.session_repository import SessionRepository

router = APIRouter(prefix="/sessions", tags=["preview"])
logger = get_logger(__name__)


@router.post("/{session_id}/preview", response_model=AppPayloadResponseSchema)
async def generate_preview(
    session_id: str,
    session_repo: SessionRepository = Depends(get_session_repository),
    conv_repo: ConversationRepository = Depends(get_conversation_repository),
    flow: PreviewFlow = Depends(get_preview_flow),
) -> AppPayloadResponseSchema:
    try:
        session = session_repo.get(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    if not session.confirmed or not session.selected_bundle_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session bundle must be confirmed before generating preview.",
        )

    extracted = ExtractedInfo(session_id=session_id)

    try:
        payload = flow.run(
            session_id=session_id,
            bundle_key=session.selected_bundle_key,
            extracted=extracted,
        )
    except BundleNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except TemplateLoadError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc

    return AppPayloadResponseSchema(
        schema_version=payload.schema_version,
        session_id=payload.session_id,
        bundle_key=payload.bundle_key,
        display_name=payload.display_name,
        modules=payload.modules,
        generation_json=payload.generation_json,
        dummy_data_json=payload.dummy_data_json,
    )
