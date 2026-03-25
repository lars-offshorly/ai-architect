"""Router: preview generation endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from api.deps import (
    get_conversation_repository,
    get_preview_flow,
    get_session_repository,
)
from api.schemas.app_payload import AppPayloadResponseSchema
from core.exceptions import BundleNotFoundError, SessionNotFoundError
from core.logging import get_logger
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
    """Run the preview pipeline for a confirmed session and return the AppPayload."""
    try:
        session = session_repo.get(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc

    if not session.confirmed or not session.selected_bundle_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session bundle must be confirmed before generating preview.",
        )

    # Pass the full conversation history so the pipeline can personalise sample data.
    # Previously this was a bare ExtractedInfo(session_id=...) with no content,
    # which meant zero personalisation was applied.
    messages = conv_repo.get_messages(session_id)
    conversation_history = [{"role": m.role, "content": m.content} for m in messages]

    try:
        payload = flow.run(
            session_id=session_id,
            bundle_key=session.selected_bundle_key,
            conversation_history=conversation_history,
        )
    except BundleNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
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
