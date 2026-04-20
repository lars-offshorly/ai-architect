"""Router: session lifecycle and conversation turn endpoints."""

from __future__ import annotations

# pylint: disable=duplicate-code
import asyncio
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from api.deps import (
    get_bundle_catalog,
    get_bundle_template_loader,
    get_conversation_flow,
    get_conversation_repository,
    get_dashboard_template_registry,
    get_session_repository,
    get_static_dashboard_output_registry,
)
from api.schemas.debug import (
    BundleCandidateInfo,
    ClassificationInfo,
    DebugInfo,
    RecommendationInfo,
)
from api.schemas.request import ConfirmBundleRequest, ReplyRequest, StartSessionRequest
from api.schemas.response import (
    ConversationTurnResponse,
    SessionStartedResponse,
)
from catalog.bundle_catalog import BundleCatalog
from core.exceptions import SessionNotFoundError
from core.logging import get_logger
from core.sanitize import sanitize_text
from domain.models.classification_result import ClassificationResult
from domain.models.conversation import ConversationMessage
from domain.models.extraction_result import ExtractionResult
from domain.models.recommendation_result import RecommendationResult
from domain.models.session import Session
from orchestrators.conversation_flow import (
    ConversationFlow,
    ConversationTurnRequest,
    TurnOptions,
)
from repositories.conversation_repository import ConversationRepository
from repositories.session_repository import SessionRepository

router = APIRouter(prefix="/sessions", tags=["sessions"])
logger = get_logger(__name__)


async def _warm_template_caches() -> None:
    """Warm BundleTemplateLoader, DashboardTemplateRegistry, and StaticDashboardOutputRegistry caches in a thread.

    Called as a FastAPI BackgroundTask after session start so templates are
    ready before the first preview request arrives.
    """
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, get_bundle_template_loader)
    await loop.run_in_executor(None, get_dashboard_template_registry)
    await loop.run_in_executor(None, get_static_dashboard_output_registry)


def _persist_result_bundle_key(session: Session, result: dict[str, object]) -> None:
    """Persist bundle_key from flow responses for pending/preview handoff flows."""
    bundle_key = result.get("bundle_key")
    if isinstance(bundle_key, str) and bundle_key:
        session.selected_bundle_key = bundle_key


def _apply_turn_result_to_session(session: Session, result: dict[str, object]) -> None:
    """Merge flow turn result into session state in-place."""
    if isinstance(result.get("classification"), ClassificationResult):
        session.latest_classification = result[
            "classification"
        ]  # type: ignore[assignment]
    if isinstance(result.get("recommendation"), RecommendationResult):
        session.latest_recommendation = result[
            "recommendation"
        ]  # type: ignore[assignment]
    extracted = result.get("extracted")
    if isinstance(extracted, ExtractionResult):
        session.accumulated_extraction = extracted
    _persist_result_bundle_key(session, result)


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


def _build_classification_info(
    classification: ClassificationResult | None,
) -> ClassificationInfo | None:
    if classification is None:
        return None
    ranked = sorted(
        classification.ranked_candidates, key=lambda item: item.confidence, reverse=True
    )
    return ClassificationInfo(
        confidence_status=classification.confidence_status,
        top_bundle_key=(
            classification.selected_bundle.bundle_key
            if classification.selected_bundle is not None
            else None
        ),
        top_confidence=classification.top_confidence,
        score_gap=classification.score_gap,
        missing_context=classification.missing_context,
        reasoning=classification.reasoning,
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


def _build_recommendation_info(
    recommendation: RecommendationResult | None,
) -> RecommendationInfo | None:
    if recommendation is None:
        return None
    return RecommendationInfo(
        recommendation_status=recommendation.recommendation_status,
        primary_bundle_key=(
            recommendation.primary_bundle.bundle_key
            if recommendation.primary_bundle is not None
            else None
        ),
        fallback_bundle_keys=[
            candidate.bundle_key for candidate in recommendation.fallback_bundles
        ],
        inferred_modules=recommendation.inferred_modules,
        reasoning=recommendation.reasoning,
    )


@router.post(
    "", response_model=SessionStartedResponse, status_code=status.HTTP_201_CREATED
)
async def start_session(
    body: StartSessionRequest,
    background_tasks: BackgroundTasks,
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
    background_tasks.add_task(_warm_template_caches)

    user_msg = ConversationMessage(role="user", content=body.message)
    conv_repo.append_message(session_id, user_msg)

    result = await flow.process_turn(
        ConversationTurnRequest(
            session_id=session_id,
            user_message=body.message,
            history=[user_msg],
            session=session,
            options=TurnOptions(preselected_intent=preselected_intent),
        )
    )
    _apply_turn_result_to_session(session, result)
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
        classification=_build_classification_info(session.latest_classification),
        recommendation=_build_recommendation_info(session.latest_recommendation),
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
        ConversationTurnRequest(
            session_id=session_id,
            user_message=body.message,
            history=history,
            session=session,
            options=TurnOptions(
                preselected_intent=session.preselected_intent,
                force_preview=body.force_preview,
            ),
        )
    )
    session.turn_count += 1
    latest_classification = session.latest_classification
    if isinstance(result.get("classification"), ClassificationResult):
        latest_classification = result["classification"]  # type: ignore[assignment]
    latest_recommendation = session.latest_recommendation
    if isinstance(result.get("recommendation"), RecommendationResult):
        latest_recommendation = result["recommendation"]  # type: ignore[assignment]
    extracted = result.get("extracted")
    if isinstance(extracted, ExtractionResult):
        session.accumulated_extraction = extracted
    if result.get("status") == "awaiting_input":
        session.clarification_turn_count += 1
    session.latest_classification = latest_classification
    session.latest_recommendation = latest_recommendation
    _persist_result_bundle_key(session, result)
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
        classification=_build_classification_info(latest_classification),
        recommendation=_build_recommendation_info(latest_recommendation),
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
