from __future__ import annotations

from dataclasses import dataclass, field
from logging import Logger
from typing import Protocol, cast

from agents.interpreter.missing_fields import MissingFieldDetector
from catalog.bundle_catalog import BundleCatalog
from core.logging import get_logger, get_session_logger
from domain.models.bundle import BundleSuggestion, SuggestedBundles
from domain.models.conversation import ConversationMessage
from domain.models.extraction_result import ExtractionResult
from domain.models.interpreter_request import InterpreterRequest

logger = get_logger(__name__)

_FlowResult = dict[str, object]

_EARLY_PREVIEW_WARNING = (
    "Preview generated with incomplete information. Some data may be generic."
)

_FORCE_PREVIEW_FALLBACK_BUNDLE = "all_microservices"

_PREVIEW_KEYWORDS = [
    "preview now",
    "show preview",
    "generate preview",
    "see preview",
    "show me the system",
    "build it now",
]


def _detect_preview_intent(user_message: str) -> bool:
    """Return True if the user message contains a recognised preview-request keyword."""
    lowered = user_message.lower()
    return any(kw in lowered for kw in _PREVIEW_KEYWORDS)


@dataclass(slots=True)
class TurnOptions:
    summary: str = ""
    preselected_intent: str | None = None
    force_preview: bool = False


@dataclass(slots=True)
class ConversationTurnRequest:
    session_id: str
    user_message: str
    history: list[ConversationMessage]
    confirmed: bool
    accumulated_extraction: ExtractionResult | None = None
    preselected_bundle_key: str | None = None
    options: TurnOptions = field(default_factory=TurnOptions)


@dataclass(slots=True)
class _TurnContext:
    extracted: ExtractionResult
    suggested: SuggestedBundles
    top: BundleSuggestion | None
    slots: dict[str, object]


class InterpreterPort(Protocol):
    async def summarize_history(
        self,
        session_id: str,
        history: list[ConversationMessage],
        extracted: ExtractionResult | None = None,
    ) -> str: ...

    async def extract_only(self, request: InterpreterRequest) -> ExtractionResult: ...

    async def interpret(
        self, request: InterpreterRequest
    ) -> tuple[ExtractionResult, SuggestedBundles]: ...

    def top_bundle(self, suggested: SuggestedBundles) -> BundleSuggestion | None: ...


class ReplierPort(Protocol):
    async def build_clarification(
        self,
        session_id: str,
        extracted: ExtractionResult,
        bundle_key: str,
    ) -> tuple[object | None, str]: ...

    async def build_bundle_suggestion(
        self,
        session_id: str,
        _suggestion: BundleSuggestion,
        slots: dict[str, object],
    ) -> str: ...


class ConversationFlow:
    def __init__(
        self,
        interpreter_service: InterpreterPort,
        replier_service: ReplierPort,
        bundle_catalog: BundleCatalog,
        required_slots_by_bundle: dict[str, list[str]],
    ) -> None:
        self._interpreter = interpreter_service
        self._replier = replier_service
        self._missing_field_detector = MissingFieldDetector(
            bundle_catalog, required_slots_by_bundle
        )

    def should_generate_early_preview(
        self, user_message: str, force_preview: bool
    ) -> bool:
        return force_preview or _detect_preview_intent(user_message)

    async def process_turn(
        self,
        request: ConversationTurnRequest | None = None,
        **kwargs: object,
    ) -> _FlowResult:
        turn_request = self._coerce_turn_request(request, kwargs)
        session_logger = get_session_logger(__name__, turn_request.session_id)
        summary_for_turn = await self._resolve_summary(turn_request)
        context = await self._resolve_turn_context(turn_request, summary_for_turn)

        if self.should_generate_early_preview(
            turn_request.user_message, turn_request.options.force_preview
        ):
            return self._build_early_preview_response(context, session_logger)

        if context.top is None:
            session_logger.info("No confident bundle — asking clarification")
            _, question = await self._replier.build_clarification(
                turn_request.session_id, context.extracted, "unknown"
            )
            return self._awaiting_input_response(question, context)

        missing_field, question = await self._replier.build_clarification(
            turn_request.session_id, context.extracted, context.top.bundle_key
        )
        if missing_field is not None:
            session_logger.info(
                "Missing field=%s for bundle=%s",
                getattr(missing_field, "value", missing_field),
                context.top.bundle_key,
            )
            return self._awaiting_input_response(question, context)

        if not turn_request.confirmed:
            message = await self._replier.build_bundle_suggestion(
                turn_request.session_id, context.top, context.slots
            )
            session_logger.info("Suggesting bundle=%s", context.top.bundle_key)
            return self._pending_confirmation_response(message, context)

        session_logger.info(
            "All slots filled and confirmed for bundle=%s", context.top.bundle_key
        )
        return self._ready_for_preview_response(context, preview_type="confirmed")

    @staticmethod
    def _coerce_turn_request(
        request: ConversationTurnRequest | None,
        kwargs: dict[str, object],
    ) -> ConversationTurnRequest:
        if request is not None:
            if kwargs:
                raise TypeError(
                    "process_turn() accepts either a ConversationTurnRequest "
                    "or keyword fields, not both."
                )
            return request

        return ConversationTurnRequest(
            session_id=cast(str, kwargs["session_id"]),
            user_message=cast(str, kwargs["user_message"]),
            history=cast(list[ConversationMessage], kwargs["history"]),
            confirmed=cast(bool, kwargs["confirmed"]),
            accumulated_extraction=cast(
                ExtractionResult | None, kwargs.get("accumulated_extraction")
            ),
            preselected_bundle_key=cast(
                str | None, kwargs.get("preselected_bundle_key")
            ),
            options=TurnOptions(
                summary=cast(str, kwargs.get("summary", "")),
                preselected_intent=cast(str | None, kwargs.get("preselected_intent")),
                force_preview=cast(bool, kwargs.get("force_preview", False)),
            ),
        )

    async def _resolve_summary(self, request: ConversationTurnRequest) -> str:
        if request.options.summary:
            return request.options.summary
        summary_history = request.history[:-1] if request.history else []
        return await self._interpreter.summarize_history(
            request.session_id, summary_history, request.accumulated_extraction
        )

    async def _resolve_turn_context(
        self,
        request: ConversationTurnRequest,
        summary_for_turn: str,
    ) -> _TurnContext:
        interpreter_request = InterpreterRequest(
            session_id=request.session_id,
            user_message=request.user_message,
            history=request.history,
            accumulated_extraction=request.accumulated_extraction,
            summary=summary_for_turn,
            preselected_intent=request.options.preselected_intent,
        )

        if request.preselected_bundle_key is not None:
            extracted = await self._interpreter.extract_only(interpreter_request)
            suggested = self._mock_preselected_suggestion(
                request.session_id, request.preselected_bundle_key
            )
            top = suggested.top()
        else:
            extracted, suggested = await self._interpreter.interpret(
                interpreter_request
            )
            top = self._interpreter.top_bundle(suggested)

        return self._build_turn_context(extracted, suggested, top)

    @staticmethod
    def _mock_preselected_suggestion(
        session_id: str, preselected_bundle_key: str
    ) -> SuggestedBundles:
        return SuggestedBundles(
            session_id=session_id,
            suggestions=[
                BundleSuggestion(
                    bundle_key=preselected_bundle_key,
                    display_name=preselected_bundle_key,
                    confidence=1.0,
                    reasoning="Pre-selected by user",
                    matched_signals=[],
                )
            ],
            top_bundle_key=preselected_bundle_key,
        )

    def _build_turn_context(
        self,
        extracted: ExtractionResult,
        suggested: SuggestedBundles,
        top: BundleSuggestion | None,
    ) -> _TurnContext:
        slots = extracted.to_extracted_info().slots
        extracted.missing_fields = self._missing_field_detector.compute(
            extracted, top.bundle_key if top is not None else None
        )
        return _TurnContext(
            extracted=extracted,
            suggested=suggested,
            top=top,
            slots=slots,
        )

    def _build_early_preview_response(
        self,
        context: _TurnContext,
        session_logger: Logger,
    ) -> _FlowResult:
        bundle_key_for_preview = self._resolve_preview_bundle_key(context)
        session_logger.info(
            "Early preview requested for bundle=%s", bundle_key_for_preview
        )
        return self._ready_for_preview_response(
            context,
            preview_type="early",
            warning=_EARLY_PREVIEW_WARNING,
            bundle_key=bundle_key_for_preview,
        )

    @staticmethod
    def _resolve_preview_bundle_key(context: _TurnContext) -> str:
        effective_top = (
            context.top if context.top is not None else context.suggested.top()
        )
        if effective_top is not None:
            return effective_top.bundle_key
        return _FORCE_PREVIEW_FALLBACK_BUNDLE

    @staticmethod
    def _awaiting_input_response(
        question: str,
        context: _TurnContext,
    ) -> _FlowResult:
        return {
            "status": "awaiting_input",
            "question": question,
            "extracted": context.extracted,
            "suggested": context.suggested,
            "slots": context.slots,
        }

    @staticmethod
    def _pending_confirmation_response(
        message: str,
        context: _TurnContext,
    ) -> _FlowResult:
        bundle_key = context.top.bundle_key if context.top is not None else None
        return {
            "status": "pending_confirmation",
            "message": message,
            "bundle_key": bundle_key,
            "extracted": context.extracted,
            "suggested": context.suggested,
            "slots": context.slots,
        }

    @staticmethod
    def _ready_for_preview_response(
        context: _TurnContext,
        preview_type: str,
        warning: str | None = None,
        bundle_key: str | None = None,
    ) -> _FlowResult:
        resolved_bundle_key = (
            bundle_key
            if bundle_key is not None
            else (context.top.bundle_key if context.top is not None else None)
        )
        return {
            "status": "ready_for_preview",
            "bundle_key": resolved_bundle_key,
            "extracted": context.extracted,
            "suggested": context.suggested,
            "slots": context.slots,
            "warning": warning,
            "preview_type": preview_type,
        }
