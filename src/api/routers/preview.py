"""Router: preview generation endpoint."""

from __future__ import annotations

# pylint: disable=duplicate-code
import json
import time
from datetime import datetime, timezone
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from langchain_openai import ChatOpenAI
from pydantic import ValidationError

from agents.preview_generator.edit.apply import apply_edit
from agents.preview_generator.edit.parse import (
    llm_parse_edit_instruction,
    parse_edit_instruction_with_fallback,
)
from agents.tenant_provisioning.validators import (
    format_manifest_validation_errors,
    validate_manifest_model,
)
from api.deps import (
    get_be_translator_client,
    get_bundle_catalog,
    get_conversation_repository,
    get_edit_llm_model,
    get_preview_flow,
    get_registry_facade,
    get_session_repository,
)
from api.schemas.app_payload import AppPayloadResponseSchema
from api.schemas.preview import EditPreviewRequestSchema
from catalog.bundle_catalog import BundleCatalog
from core.exceptions import (
    BundleNotFoundError,
    InvalidPayloadError,
    PreviewGenerationError,
    SessionNotFoundError,
)
from core.logging import get_logger
from core.metrics import metrics
from domain.models.extraction_result import ExtractionResult
from domain.services.be_translator import BEOperation, BETranslatorClient
from domain.services.early_preview_policy import (
    resolve_early_bundle_key,
)
from domain.services.registry_facade import RegistryFacade
from orchestrators.preview_flow import PreviewFlow
from repositories.conversation_repository import ConversationRepository
from repositories.session_repository import SessionRepository

router = APIRouter(prefix="/sessions", tags=["preview"])
logger = get_logger(__name__)

_EARLY_PREVIEW_WARNING = (
    "Preview generated with incomplete information. Some data may be generic."
)


def _json_size_bytes(payload: object) -> int:
    return len(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )


def _manifest_counts(payload: dict[str, Any]) -> dict[str, int]:
    manifest = payload.get("manifest")
    if not isinstance(manifest, dict):
        return {"modules": 0, "queues": 0, "dashboards": 0, "kpis": 0}
    modules = payload.get("modules")
    modules_count = len(modules) if isinstance(modules, list) else 0
    tickets = manifest.get("tickets", {})
    dashboard = manifest.get("dashboard", {})
    kpi = manifest.get("kpi", {})
    queues = tickets.get("queues", []) if isinstance(tickets, dict) else []
    dashboards = dashboard.get("dashboards", []) if isinstance(dashboard, dict) else []
    kpis = kpi.get("kpis", []) if isinstance(kpi, dict) else []
    return {
        "modules": modules_count,
        "queues": len(queues) if isinstance(queues, list) else 0,
        "dashboards": len(dashboards) if isinstance(dashboards, list) else 0,
        "kpis": len(kpis) if isinstance(kpis, list) else 0,
    }


def _warning_code(warning: str | None) -> str:
    if not warning:
        return "none"
    if ":" not in warning:
        return "uncoded"
    return warning.split(":", 1)[0].strip() or "uncoded"


def _format_preview_warnings(
    preview_warnings: Any, existing_warning: str | None
) -> str | None:
    if not isinstance(preview_warnings, list) or not preview_warnings:
        return existing_warning
    codes = [
        str(item.get("code"))
        for item in preview_warnings
        if isinstance(item, dict) and item.get("code")
    ]
    degraded_warning = (
        f"Preview generated with degraded enrichment: {', '.join(codes)}"
        if codes
        else "Preview generated with degraded enrichment."
    )
    return (
        f"{existing_warning} {degraded_warning}".strip()
        if existing_warning
        else degraded_warning
    )


def _operation_from_action(action_type: str) -> BEOperation:
    lowered = action_type.lower()
    if "rename" in lowered:
        return "rename"
    if lowered.startswith("remove_"):
        return "remove"
    return "edit"


async def _dispatch_preview_to_be_translator(
    *,
    session: Any,
    session_repo: SessionRepository,
    translator_client: BETranslatorClient,
    operation: BEOperation,
    payload: AppPayloadResponseSchema,
) -> None:
    session.be_translator_revision = int(session.be_translator_revision or 0) + 1
    session_repo.save(session)
    request_id = str(uuid4())
    preview_json = payload.model_dump(mode="json")
    try:
        await translator_client.translate_preview(
            request_id=request_id,
            document_id=payload.session_id,
            revision=session.be_translator_revision,
            operation=operation,
            preview_json={
                "requestId": request_id,
                "documentId": payload.session_id,
                "revision": session.be_translator_revision,
                "operation": operation,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "previewJson": preview_json,
            },
        )
        metrics.inc("be_translator.requests.total")
        metrics.inc(f"be_translator.requests.{operation}")
    except Exception as exc:  # pylint: disable=broad-except
        metrics.inc("be_translator.errors.total")
        logger.warning(
            "be_translator_dispatch_failed session=%s revision=%s operation=%s err=%s",
            payload.session_id,
            session.be_translator_revision,
            operation,
            exc,
        )


async def _execute_preview_pipeline(
    session_id: str,
    bundle_key: str,
    conv_repo: ConversationRepository,
    flow: PreviewFlow,
    registry_facade: RegistryFacade,
    catalog: BundleCatalog,
    preview_type: str | None = None,
    warning: str | None = None,
    extraction_result: ExtractionResult | None = None,
    preselected_intent: str | None = None,
) -> AppPayloadResponseSchema:
    # pylint: disable=too-many-locals
    """Execute the preview pipeline and assemble the response schema."""
    start = time.perf_counter()
    if not registry_facade.has_bundle(bundle_key) and not catalog.has_bundle(
        bundle_key
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bundle not found: {bundle_key}",
        )

    messages = conv_repo.get_messages(session_id)
    if not messages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "No conversation history found. "
                "Preview requires at least one prompt."
            ),
        )

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

    manifest = payload.manifest
    warning = _format_preview_warnings([], warning)

    response = AppPayloadResponseSchema(
        schema_version="2.0",
        session_id=payload.session_id,
        bundle_key=payload.bundle_key,
        display_name=payload.display_name,
        modules=payload.modules,
        preview_type=preview_type,
        warning=warning,
        manifest=manifest,
    )
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    metrics.inc("preview.requests.total")
    if elapsed_ms >= 1000:
        metrics.inc("preview.latency.ge_1000ms")
    logger.info(
        "preview_event session=%s bundle=%s preview_type=%s elapsed_ms=%s",
        session_id,
        bundle_key,
        preview_type,
        elapsed_ms,
    )
    return response


@router.post("/{session_id}/preview", response_model=AppPayloadResponseSchema)
async def generate_preview(
    session_id: str,
    session_repo: Annotated[SessionRepository, Depends(get_session_repository)],
    conv_repo: Annotated[ConversationRepository, Depends(get_conversation_repository)],
    flow: Annotated[PreviewFlow, Depends(get_preview_flow)],
    registry_facade: Annotated[RegistryFacade, Depends(get_registry_facade)],
    catalog: Annotated[BundleCatalog, Depends(get_bundle_catalog)],
    translator_client: Annotated[BETranslatorClient, Depends(get_be_translator_client)],
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

    response = await _execute_preview_pipeline(
        session_id=session_id,
        bundle_key=session.selected_bundle_key,
        conv_repo=conv_repo,
        flow=flow,
        registry_facade=registry_facade,
        catalog=catalog,
        preview_type="confirmed",
        extraction_result=session.accumulated_extraction,
        preselected_intent=session.preselected_intent,
    )
    await _dispatch_preview_to_be_translator(
        session=session,
        session_repo=session_repo,
        translator_client=translator_client,
        operation="create",
        payload=response,
    )
    return response


@router.post("/{session_id}/preview/early", response_model=AppPayloadResponseSchema)
async def generate_early_preview(
    session_id: str,
    session_repo: Annotated[SessionRepository, Depends(get_session_repository)],
    conv_repo: Annotated[ConversationRepository, Depends(get_conversation_repository)],
    flow: Annotated[PreviewFlow, Depends(get_preview_flow)],
    registry_facade: Annotated[RegistryFacade, Depends(get_registry_facade)],
    catalog: Annotated[BundleCatalog, Depends(get_bundle_catalog)],
    translator_client: Annotated[BETranslatorClient, Depends(get_be_translator_client)],
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

    resolved_key = resolve_early_bundle_key(session)
    logger.info(
        "Early preview for session=%s using bundle=%s", session_id, resolved_key
    )

    response = await _execute_preview_pipeline(
        session_id=session_id,
        bundle_key=resolved_key,
        conv_repo=conv_repo,
        flow=flow,
        registry_facade=registry_facade,
        catalog=catalog,
        preview_type="early",
        warning=_EARLY_PREVIEW_WARNING,
        extraction_result=session.accumulated_extraction,
        preselected_intent=session.preselected_intent,
    )
    await _dispatch_preview_to_be_translator(
        session=session,
        session_repo=session_repo,
        translator_client=translator_client,
        operation="create",
        payload=response,
    )
    return response


@router.post("/{session_id}/preview/edit", response_model=AppPayloadResponseSchema)
async def edit_preview(
    session_id: str,
    body: EditPreviewRequestSchema,
    request: Request,
    session_repo: Annotated[SessionRepository, Depends(get_session_repository)],
    catalog: Annotated[BundleCatalog, Depends(get_bundle_catalog)],
    edit_llm_model: Annotated[ChatOpenAI | None, Depends(get_edit_llm_model)],
    translator_client: Annotated[BETranslatorClient, Depends(get_be_translator_client)],
) -> AppPayloadResponseSchema:
    """Apply a natural-language edit to an existing preview payload.

    Accepts the full current preview + an instruction string.
    Parses the instruction into an EditAction, applies it to the payload,
    and returns the updated AppPayloadResponseSchema.

    No pipeline re-run — purely client-side JSON mutation.
    """
    # pylint: disable=too-many-locals
    try:
        session = session_repo.get(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc

    start = time.perf_counter()
    from core.config import get_settings

    settings = get_settings()
    preview_bytes = _json_size_bytes(body.current_preview)
    if preview_bytes > settings.MAX_EDIT_PREVIEW_BYTES:
        metrics.inc("edit.rejected.payload_too_large")
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"current_preview payload too large: {preview_bytes} bytes "
                f"(max {settings.MAX_EDIT_PREVIEW_BYTES})"
            ),
        )
    action = parse_edit_instruction_with_fallback(
        body.instruction,
        catalog,
        llm_parser=(
            (
                lambda instruction: llm_parse_edit_instruction(
                    instruction, edit_llm_model
                )
            )
            if edit_llm_model is not None
            else None
        ),
        enabled=settings.EDIT_LLM_FALLBACK_ENABLED,
        timeout_ms=settings.EDIT_LLM_TIMEOUT_MS,
        max_retries=settings.EDIT_LLM_MAX_RETRIES,
        cb_threshold=settings.EDIT_LLM_CB_THRESHOLD,
        cb_cooldown_sec=settings.EDIT_LLM_CB_COOLDOWN_SEC,
    )
    current_preview = dict(body.current_preview)
    v2_schema_version = (
        current_preview.get("manifest", {}).get("schema_version")
        if isinstance(current_preview.get("manifest"), dict)
        else None
    )
    if v2_schema_version != "2.0":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="current_preview.manifest (schema_version=2.0) is required.",
        )
    try:
        validate_manifest_model(current_preview["manifest"])
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "manifest_validation_error",
                "errors": format_manifest_validation_errors(exc),
            },
        ) from exc
    before_counts = _manifest_counts(current_preview)
    updated, warning = apply_edit(current_preview, action, catalog)
    after_counts = _manifest_counts(updated)
    warning_code = _warning_code(warning)
    outcome = "success" if warning is None else "warning"

    metrics.inc("edit.requests.total")
    metrics.inc(f"edit.actions.{action.action_type.value}")
    metrics.inc(f"edit.outcome.{outcome}")
    if warning is not None:
        metrics.inc(f"edit.warning.{warning_code}")

    logger.info(
        (
            "edit_event session=%s action=%s target=%s outcome=%s warning_code=%s "
            "before=%s after=%s instruction=%r"
        ),
        session_id,
        action.action_type.value,
        action.target,
        outcome,
        warning_code,
        before_counts,
        after_counts,
        body.instruction,
    )
    client_ip = request.headers.get("x-forwarded-for") or (
        request.client.host if request.client is not None else "unknown"
    )
    logger.info(
        (
            "audit_edit session=%s ip=%s action=%s target=%s outcome=%s "
            "warning_code=%s before=%s after=%s"
        ),
        session_id,
        client_ip,
        action.action_type.value,
        action.target,
        outcome,
        warning_code,
        before_counts,
        after_counts,
    )

    response = AppPayloadResponseSchema(
        schema_version="2.0",
        session_id=updated.get("session_id", session_id),
        bundle_key=updated.get("bundle_key", ""),
        display_name=updated.get("display_name", ""),
        modules=updated.get("modules", []),
        preview_type=updated.get("preview_type"),
        warning=warning,
        manifest=updated.get("manifest", {}),
    )
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    if elapsed_ms >= 500:
        metrics.inc("edit.latency.ge_500ms")
    logger.info(
        "edit_latency session=%s elapsed_ms=%s payload_bytes=%s",
        session_id,
        elapsed_ms,
        preview_bytes,
    )
    await _dispatch_preview_to_be_translator(
        session=session,
        session_repo=session_repo,
        translator_client=translator_client,
        operation=_operation_from_action(action.action_type.value),
        payload=response,
    )
    return response
