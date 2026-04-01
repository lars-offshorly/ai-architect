"""Router: preview generation endpoint."""

from __future__ import annotations

# pylint: disable=duplicate-code
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from agents.preview_generator.edit.apply import apply_edit
from agents.preview_generator.edit.parse import parse_edit_instruction
from api.deps import (
    get_conversation_repository,
    get_preview_flow,
    get_session_repository,
)
from api.schemas.app_payload import AppPayloadResponseSchema
from api.schemas.preview import EditPreviewRequestSchema
from core.exceptions import BundleNotFoundError, SessionNotFoundError
from core.logging import get_logger
from domain.models.extraction_result import ExtractionResult
from domain.models.session import Session
from orchestrators.preview_flow import PreviewFlow
from repositories.conversation_repository import ConversationRepository
from repositories.session_repository import SessionRepository

router = APIRouter(prefix="/sessions", tags=["preview"])
logger = get_logger(__name__)

_EARLY_PREVIEW_WARNING = (
    "Preview generated with incomplete information. Some data may be generic."
)
_FALLBACK_BUNDLE_KEY = "all_microservices"


def _run_preview_pipeline(
    session_id: str,
    bundle_key: str,
    conv_repo: ConversationRepository,
    flow: PreviewFlow,
    warning: str | None = None,
    extraction_result: ExtractionResult | None = None,
    preselected_intent: str | None = None,
) -> AppPayloadResponseSchema:
    """Execute the preview pipeline and assemble the response schema."""
    messages = conv_repo.get_messages(session_id)
    conversation_history = [{"role": m.role, "content": m.content} for m in messages]

    try:
        payload = flow.run(
            session_id=session_id,
            bundle_key=bundle_key,
            conversation_history=conversation_history,
            extraction_result=extraction_result,
            preselected_intent=preselected_intent,
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
        warning=warning,
    )


def _resolve_early_bundle_key(session: Session) -> str:
    """Return the best available bundle key for an early (unconfirmed) preview.

    Priority order:
      1. selected_bundle_key  — confirmed after conversation
      2. preselected_bundle_key — user chose before chatting (Lars scenario #1)
      3. latest_classification.top_bundle_key — classifier's best guess mid-conversation
      4. _FALLBACK_BUNDLE_KEY — "preview system now" with no classification yet (#3)
    """
    if session.selected_bundle_key:
        return session.selected_bundle_key
    if session.preselected_bundle_key:
        return session.preselected_bundle_key
    if session.latest_classification:
        top_key = session.latest_classification.get("top_bundle_key")
        if top_key:
            return top_key
    return _FALLBACK_BUNDLE_KEY


@router.post("/{session_id}/preview", response_model=AppPayloadResponseSchema)
async def generate_preview(
    session_id: str,
    session_repo: Annotated[SessionRepository, Depends(get_session_repository)],
    conv_repo: Annotated[ConversationRepository, Depends(get_conversation_repository)],
    flow: Annotated[PreviewFlow, Depends(get_preview_flow)],
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

    return _run_preview_pipeline(
        session_id=session_id,
        bundle_key=session.selected_bundle_key,
        conv_repo=conv_repo,
        flow=flow,
        extraction_result=session.accumulated_extraction,
        preselected_intent=session.preselected_intent,
    )


@router.post("/{session_id}/preview/early", response_model=AppPayloadResponseSchema)
async def generate_early_preview(
    session_id: str,
    session_repo: Annotated[SessionRepository, Depends(get_session_repository)],
    conv_repo: Annotated[ConversationRepository, Depends(get_conversation_repository)],
    flow: Annotated[PreviewFlow, Depends(get_preview_flow)],
) -> AppPayloadResponseSchema:
    """Generate a preview without requiring bundle confirmation.

    Uses the best available bundle key in priority order:
      selected > preselected > latest classification > all_microservices fallback.
    Always returns a warning indicating the preview may be incomplete.
    Supports Lars scenario #3: "preview system now" from the very first prompt.
    """
    try:
        session = session_repo.get(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc

    bundle_key = _resolve_early_bundle_key(session)
    logger.info("Early preview for session=%s using bundle=%s", session_id, bundle_key)

    return _run_preview_pipeline(
        session_id=session_id,
        bundle_key=bundle_key,
        conv_repo=conv_repo,
        flow=flow,
        warning=_EARLY_PREVIEW_WARNING,
        extraction_result=session.accumulated_extraction,
        preselected_intent=session.preselected_intent,
    )


@router.post("/{session_id}/preview/edit", response_model=AppPayloadResponseSchema)
async def edit_preview(
    session_id: str,
    body: EditPreviewRequestSchema,
    session_repo: Annotated[SessionRepository, Depends(get_session_repository)],
) -> AppPayloadResponseSchema:
    """Apply a natural-language edit to an existing preview payload.

    Accepts the full current preview + an instruction string.
    Parses the instruction into an EditAction, applies it to the payload,
    and returns the updated AppPayloadResponseSchema.

    No pipeline re-run — purely client-side JSON mutation.
    """
    try:
        session_repo.get(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc

    action = parse_edit_instruction(body.instruction)
    updated, warning = apply_edit(dict(body.current_preview), action)

    logger.info(
        "Edit preview session=%s action=%s target=%s warning=%s",
        session_id,
        action.action_type.value,
        action.target,
        warning,
    )

    return AppPayloadResponseSchema(
        schema_version=updated.get("schema_version", "1.0"),
        session_id=updated.get("session_id", session_id),
        bundle_key=updated.get("bundle_key", ""),
        display_name=updated.get("display_name", ""),
        modules=updated.get("modules", []),
        generation_json=updated.get("generation_json", {}),
        dummy_data_json=updated.get("dummy_data_json", {}),
        warning=warning,
    )
