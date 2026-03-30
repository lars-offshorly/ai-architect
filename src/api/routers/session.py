"""Router: session lifecycle and conversation turn endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from api.deps import (
    get_bundle_catalog,
    get_conversation_flow,
    get_conversation_repository,
    get_session_repository,
)
from api.schemas.debug import BundleCandidateInfo, ClassificationInfo, DebugInfo
from api.schemas.request import ConfirmBundleRequest, ReplyRequest, StartSessionRequest
from api.schemas.response import (
    ConversationTurnResponse,
    SessionStartedResponse,
)
from catalog.bundle_catalog import BundleCatalog
from core.config import get_settings
from core.exceptions import SessionNotFoundError
from core.logging import get_logger
from core.sanitize import sanitize_text
from domain.models.bundle import SuggestedBundles
from domain.models.conversation import ConversationMessage
from domain.models.extraction_result import ExtractionResult
from domain.models.session import Session
from orchestrators.conversation_flow import ConversationFlow
from repositories.conversation_repository import ConversationRepository
from repositories.session_repository import SessionRepository

router = APIRouter(prefix="/sessions", tags=["sessions"])
logger = get_logger(__name__)


def _get_confidence_threshold() -> float:
    try:
        return get_settings().CONFIDENCE_THRESHOLD
    except Exception:  # pylint: disable=broad-exception-caught
        return 0.6


def _build_debug_info(extracted: ExtractionResult | None) -> DebugInfo | None:
    if extracted is None:
        return None
    cs = extracted.classification_signals
    ps = extracted.personalization_signals
    personalization = {
        "company_name": ps.company_name,
        "employee_names": ps.employee_names,
        "role_names": ps.role_names,
        "department_names": ps.department_names,
        "branch_names": ps.branch_names,
        "custom_labels": ps.custom_labels,
        "terminology": ps.terminology,
    }
    return DebugInfo(
        extracted_keywords=cs.keywords,
        extracted_entities=cs.entities,
        extracted_intents=cs.intents,
        extracted_workflow_hints=cs.workflow_hints,
        missing_fields=[field.value for field in extracted.missing_fields],
        personalization=personalization,
    )


def _build_classification_info(suggested: object) -> ClassificationInfo | None:
    if not isinstance(suggested, SuggestedBundles):
        return None
    threshold = _get_confidence_threshold()
    top = suggested.top()
    confidence_status = (
        "proceed" if top is not None and top.confidence >= threshold else "clarify"
    )
    ranked = sorted(
        suggested.suggestions, key=lambda item: item.confidence, reverse=True
    )
    return ClassificationInfo(
        confidence_status=confidence_status,
        top_bundle_key=top.bundle_key if top is not None else None,
        ranked_candidates=[
            BundleCandidateInfo(
                bundle_key=item.bundle_key,
                display_name=item.display_name,
                confidence=item.confidence,
                reasoning=item.reasoning,
                matched_signals=item.matched_signals,
            )
            for item in ranked
        ],
    )


@router.post(
    "", response_model=SessionStartedResponse, status_code=status.HTTP_201_CREATED
)
async def start_session(
    body: StartSessionRequest,
    session_repo: Annotated[SessionRepository, Depends(get_session_repository)],
    conv_repo: Annotated[ConversationRepository, Depends(get_conversation_repository)],
    flow: Annotated[ConversationFlow, Depends(get_conversation_flow)],
    catalog: Annotated[BundleCatalog, Depends(get_bundle_catalog)],
) -> SessionStartedResponse:
    """Create a new session and process the opening user message."""
    preselected_bundle_key: str | None = None
    if body.preselected_bundle_key is not None:
        preselected_bundle_key = sanitize_text(
            body.preselected_bundle_key, max_length=100
        )
        if not catalog.has_bundle(preselected_bundle_key):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown bundle key: '{preselected_bundle_key}'.",
            )

    preselected_intent: str | None = None
    if body.preselected_intent is not None:
        preselected_intent = sanitize_text(
            body.preselected_intent, max_length=100
        ).lower()
        known_intents = catalog.get_all_typical_intents()
        if preselected_intent not in known_intents:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Unknown intent: '{preselected_intent}'. "
                    f"Valid intents: {known_intents}"
                ),
            )

    session_id = str(uuid4())
    session = Session(session_id=session_id, user_id=body.user_id)
    if preselected_bundle_key is not None:
        session.selected_bundle_key = preselected_bundle_key
        session.preselected_bundle_key = preselected_bundle_key
    if preselected_intent is not None:
        session.preselected_intent = preselected_intent
    session_repo.save(session)

    user_msg = ConversationMessage(role="user", content=body.message)
    conv_repo.append_message(session_id, user_msg)

    result = await flow.process_turn(
        session_id=session_id,
        user_message=body.message,
        accumulated_extraction=None,
        history=[user_msg],
        confirmed=False,
        preselected_bundle_key=preselected_bundle_key,
        preselected_intent=preselected_intent,
    )

    if result.get("bundle_key"):
        session.selected_bundle_key = result["bundle_key"]  # type: ignore[assignment]
    if result.get("extracted") is not None:
        session.accumulated_extraction = result["extracted"]
    if result.get("status") == "awaiting_input":
        session.clarification_turn_count += 1
    suggested = result.get("suggested")
    if isinstance(suggested, SuggestedBundles):
        top_candidate = suggested.top()
        session.latest_classification = {
            "top_bundle_key": (
                top_candidate.bundle_key if top_candidate is not None else None
            ),
        }
    session_repo.save(session)

    return SessionStartedResponse(
        status=result["status"],  # type: ignore[arg-type]
        session_id=session_id,
        message=result.get("message"),  # type: ignore[arg-type]
        question=result.get("question"),  # type: ignore[arg-type]
        bundle_key=result.get("bundle_key"),  # type: ignore[arg-type]
        slots=result.get("slots", {}),  # type: ignore[arg-type]
        warning=result.get("warning"),  # type: ignore[arg-type]
        preview_type=result.get("preview_type"),  # type: ignore[arg-type]
        debug=_build_debug_info(result.get("extracted")),  # type: ignore[arg-type]
        classification=_build_classification_info(result.get("suggested")),
        recommendation=None,
    )


@router.post("/{session_id}/reply", response_model=ConversationTurnResponse)
async def reply_to_session(
    session_id: str,
    body: ReplyRequest,
    session_repo: Annotated[SessionRepository, Depends(get_session_repository)],
    conv_repo: Annotated[ConversationRepository, Depends(get_conversation_repository)],
    flow: Annotated[ConversationFlow, Depends(get_conversation_flow)],
) -> ConversationTurnResponse:
    """Append a user reply and run the next conversation turn."""
    try:
        session = session_repo.get(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc

    user_msg = ConversationMessage(role="user", content=body.message)
    conv_repo.append_message(session_id, user_msg)
    history = conv_repo.get_messages(session_id)

    result = await flow.process_turn(
        session_id=session_id,
        user_message=body.message,
        accumulated_extraction=session.accumulated_extraction,
        history=history,
        confirmed=session.confirmed,
        preselected_bundle_key=session.preselected_bundle_key,
        preselected_intent=session.preselected_intent,
        force_preview=body.force_preview,
    )
    session.turn_count += 1
    if result.get("bundle_key"):
        session.selected_bundle_key = result["bundle_key"]  # type: ignore[assignment]
    if result.get("extracted") is not None:
        session.accumulated_extraction = result["extracted"]
    if result.get("status") == "awaiting_input":
        session.clarification_turn_count += 1
    reply_suggested = result.get("suggested")
    if isinstance(reply_suggested, SuggestedBundles):
        top_candidate = reply_suggested.top()
        session.latest_classification = {
            "top_bundle_key": (
                top_candidate.bundle_key if top_candidate is not None else None
            ),
        }
    session_repo.save(session)

    return ConversationTurnResponse(
        status=result["status"],  # type: ignore[arg-type]
        session_id=session_id,
        message=result.get("message"),  # type: ignore[arg-type]
        question=result.get("question"),  # type: ignore[arg-type]
        bundle_key=result.get("bundle_key"),  # type: ignore[arg-type]
        slots=result.get("slots", {}),  # type: ignore[arg-type]
        warning=result.get("warning"),  # type: ignore[arg-type]
        preview_type=result.get("preview_type"),  # type: ignore[arg-type]
        debug=_build_debug_info(result.get("extracted")),  # type: ignore[arg-type]
        classification=_build_classification_info(result.get("suggested")),
        recommendation=None,
    )


@router.post("/{session_id}/confirm", response_model=ConversationTurnResponse)
async def confirm_bundle(
    session_id: str,
    body: ConfirmBundleRequest,
    session_repo: Annotated[SessionRepository, Depends(get_session_repository)],
) -> ConversationTurnResponse:
    """Confirm or reject the proposed bundle, updating session state accordingly."""
    try:
        session = session_repo.get(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc

    session.confirmed = body.confirmed
    session_repo.save(session)

    return ConversationTurnResponse(
        status="ready_for_preview" if body.confirmed else "in_progress",
        session_id=session_id,
        bundle_key=session.selected_bundle_key,
        preview_type="confirmed" if body.confirmed else None,
    )
