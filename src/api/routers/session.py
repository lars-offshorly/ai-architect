from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from api.deps import (
    get_conversation_flow,
    get_conversation_repository,
    get_session_repository,
)
from api.schemas.request import ConfirmBundleRequest, ReplyRequest, StartSessionRequest
from api.schemas.response import ConversationTurnResponse, ErrorResponse, SessionStartedResponse
from core.exceptions import SessionNotFoundError
from core.logging import get_logger
from domain.models.conversation import ConversationMessage
from domain.models.session import Session
from orchestrators.conversation_flow import ConversationFlow
from repositories.conversation_repository import ConversationRepository
from repositories.session_repository import SessionRepository

router = APIRouter(prefix="/sessions", tags=["sessions"])
logger = get_logger(__name__)


@router.post("", response_model=SessionStartedResponse, status_code=status.HTTP_201_CREATED)
async def start_session(
    body: StartSessionRequest,
    session_repo: SessionRepository = Depends(get_session_repository),
    conv_repo: ConversationRepository = Depends(get_conversation_repository),
    flow: ConversationFlow = Depends(get_conversation_flow),
) -> SessionStartedResponse:
    session_id = str(uuid4())
    session = Session(session_id=session_id, user_id=body.user_id)
    session_repo.save(session)

    user_msg = ConversationMessage(role="user", content=body.message)
    conv_repo.append_message(session_id, user_msg)

    result = await flow.process_turn(
        session_id=session_id,
        user_message=body.message,
        existing_slots={},
        history=[user_msg],
        confirmed=False,
    )

    if result.get("bundle_key"):
        session.selected_bundle_key = result["bundle_key"]  # type: ignore[assignment]
        session_repo.save(session)

    return SessionStartedResponse(
        status=result["status"],  # type: ignore[arg-type]
        session_id=session_id,
        message=result.get("message"),  # type: ignore[arg-type]
        question=result.get("question"),  # type: ignore[arg-type]
        bundle_key=result.get("bundle_key"),  # type: ignore[arg-type]
        slots=result.get("slots", {}),  # type: ignore[arg-type]
    )


@router.post("/{session_id}/reply", response_model=ConversationTurnResponse)
async def reply_to_session(
    session_id: str,
    body: ReplyRequest,
    session_repo: SessionRepository = Depends(get_session_repository),
    conv_repo: ConversationRepository = Depends(get_conversation_repository),
    flow: ConversationFlow = Depends(get_conversation_flow),
) -> ConversationTurnResponse:
    try:
        session = session_repo.get(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    user_msg = ConversationMessage(role="user", content=body.message)
    conv_repo.append_message(session_id, user_msg)
    history = conv_repo.get_messages(session_id)

    extracted_info = getattr(session, "_last_extracted", None)
    existing_slots: dict[str, object] = {}
    if extracted_info is not None:
        existing_slots = getattr(extracted_info, "slots", {})

    result = await flow.process_turn(
        session_id=session_id,
        user_message=body.message,
        existing_slots=existing_slots,
        history=history,
        confirmed=session.confirmed,
    )
    session.turn_count += 1
    if result.get("bundle_key"):
        session.selected_bundle_key = result["bundle_key"]  # type: ignore[assignment]
    session_repo.save(session)

    return ConversationTurnResponse(
        status=result["status"],  # type: ignore[arg-type]
        session_id=session_id,
        message=result.get("message"),  # type: ignore[arg-type]
        question=result.get("question"),  # type: ignore[arg-type]
        bundle_key=result.get("bundle_key"),  # type: ignore[arg-type]
        slots=result.get("slots", {}),  # type: ignore[arg-type]
    )


@router.post("/{session_id}/confirm", response_model=ConversationTurnResponse)
async def confirm_bundle(
    session_id: str,
    body: ConfirmBundleRequest,
    session_repo: SessionRepository = Depends(get_session_repository),
) -> ConversationTurnResponse:
    try:
        session = session_repo.get(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    session.confirmed = body.confirmed
    session_repo.save(session)

    return ConversationTurnResponse(
        status="ready_for_preview" if body.confirmed else "in_progress",
        session_id=session_id,
        bundle_key=session.selected_bundle_key,
    )
