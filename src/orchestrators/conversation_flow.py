from __future__ import annotations

from dataclasses import dataclass, field
from logging import LoggerAdapter
from typing import Any, Protocol, cast

from agents.interpreter.fallback import FallbackHandler
from agents.interpreter.missing_fields import MissingFieldDetector
from catalog.bundle_catalog import BundleCatalog
from core.config import get_settings
from core.logging import get_logger, get_session_logger
from domain.models.bundle import BundleSuggestion
from domain.models.classification_result import ClassificationResult
from domain.models.conversation import ConversationMessage
from domain.models.extraction_result import ExtractionResult
from domain.models.interpreter_request import InterpreterRequest
from domain.models.recommendation_result import RecommendationResult
from domain.models.session import Session
from domain.services.bundle_recommendation import BundleRecommendationService

logger = get_logger(__name__)

_FlowResult = dict[str, object]

_EARLY_PREVIEW_WARNING = (
    "Preview generated with incomplete information. Some data may be generic."
)

_FORCE_PREVIEW_FALLBACK_BUNDLE = "generic"

_PREVIEW_KEYWORDS = [
    "preview now",
    "show preview",
    "generate preview",
    "see preview",
    "show me the system",
    "build it now",
]

_CONFIRMATION_PHRASES = [
    "go ahead",
    "proceed",
    "looks good",
    "yes please",
    "sounds good",
    "confirm",
    "do it",
    "that works",
    "let's do it",
    "yes",
]

_NEGATION_WORDS = ["don't", "dont", "do not", "not", "never", "no"]


def _detect_preview_intent(user_message: str) -> bool:
    """Return True if the user message contains a recognised preview-request keyword."""
    lowered = user_message.lower()
    return any(kw in lowered for kw in _PREVIEW_KEYWORDS)


def _detect_confirmation_intent(user_message: str) -> bool:
    """Return True if the message expresses confirmation and is not negated.

    Negation-aware: a negation word immediately preceding the phrase (within
    three tokens) suppresses the match.  A leading "no" followed by a comma
    and a confirmation phrase (e.g. "no, go ahead") is NOT treated as negation
    because the comma separates the clauses.
    """
    lowered = user_message.lower()
    for phrase in _CONFIRMATION_PHRASES:
        if phrase not in lowered:
            continue
        phrase_start = lowered.index(phrase)
        preceding = lowered[:phrase_start]
        # Strip punctuation that acts as a clause boundary (comma, period, etc.)
        # so "no, go ahead" is not negated.
        clause_boundary = max(
            preceding.rfind(","),
            preceding.rfind("."),
            preceding.rfind("!"),
            preceding.rfind(";"),
        )
        text_before_phrase = preceding[clause_boundary + 1 :]
        tokens = text_before_phrase.split()
        nearby_tokens = tokens[-3:] if len(tokens) > 3 else tokens
        if any(neg in nearby_tokens for neg in _NEGATION_WORDS):
            continue
        return True
    return False


@dataclass(slots=True)
class TurnOptions:
    summary: str = ""
    preselected_intent: str | None = None
    force_preview: bool = False


@dataclass(slots=True)
# pylint: disable=too-many-instance-attributes
class ConversationTurnRequest:
    session_id: str
    user_message: str
    history: list[ConversationMessage]

    # Canonical Week 3 input.
    session: Session | None = None

    # Legacy compatibility fields (kept for existing tests/callers).
    confirmed: bool = False
    accumulated_extraction: ExtractionResult | None = None
    preselected_bundle_key: str | None = None

    options: TurnOptions = field(default_factory=TurnOptions)


@dataclass(slots=True)
class _TurnContext:
    extracted: ExtractionResult
    classification: ClassificationResult
    recommendation: RecommendationResult
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
    ) -> tuple[ExtractionResult, ClassificationResult]: ...

    def top_bundle(
        self, _suggested: ClassificationResult
    ) -> BundleSuggestion | None: ...


class ReplierPort(Protocol):
    async def build_clarification(
        self,
        session_id: str,
        extracted: ExtractionResult,
        bundle_key: str,
        history: list[ConversationMessage] | None = None,
    ) -> tuple[object | None, str]: ...

    async def build_bundle_verification_question(
        self,
        session_id: str,
        display_name: str,
        slots: dict[str, object],
        history: list[ConversationMessage] | None = None,
    ) -> str: ...

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
        self._fallback_handler = FallbackHandler(
            bundle_catalog,
            proceed_threshold=self._setting_or_default(
                "CONFIDENCE_PROCEED_THRESHOLD", 0.75
            ),
            suggest_threshold=self._setting_or_default(
                "CONFIDENCE_SUGGEST_THRESHOLD", 0.50
            ),
            score_gap_minimum=self._setting_or_default("SCORE_GAP_MINIMUM", 0.15),
            max_clarification_turns=int(
                self._setting_or_default("MAX_CLARIFICATION_TURNS", 3)
            ),
        )
        self._recommendation_service = BundleRecommendationService(bundle_catalog)

    @staticmethod
    def _setting_or_default(name: str, default: float | int) -> float | int:
        try:
            return cast(float | int, getattr(get_settings(), name))
        except (AttributeError, TypeError, ValueError):
            return default

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
        session = self._resolve_session(turn_request)
        session_logger = get_session_logger(__name__, turn_request.session_id)

        summary_for_turn = await self._resolve_summary(turn_request, session)
        context = await self._resolve_turn_context(
            turn_request,
            session,
            summary_for_turn,
        )

        if self.should_generate_early_preview(
            turn_request.user_message, turn_request.options.force_preview
        ):
            result = self._build_early_preview_response(context, session_logger)
            self._persist_session_state(session, context, result)
            return result

        # Always ask exactly one verification question on the first unconfirmed turn,
        # regardless of confidence, to collect user context and confirm the bundle fit.
        # This runs before all confidence-based branching so every path gets the same
        # smart follow-up on turn 1.
        if (
            session.clarification_turn_count == 0
            and not session.confirmed
            and session.preselected_bundle_key is None
        ):
            top_display = context.top.display_name if context.top is not None else ""
            question = await self._replier.build_bundle_verification_question(
                turn_request.session_id,
                top_display,
                context.slots,
                history=turn_request.history,
            )
            result = self._awaiting_input_response(question, context)
            self._persist_session_state(session, context, result)
            return result

        status = context.classification.confidence_status

        if (
            status in {"clarify", "suggest_alternatives"}
            and not session.confirmed
            and session.preselected_bundle_key is None
        ):
            question = await self._build_awaiting_question(turn_request, context)
            result = self._awaiting_input_response(question, context)
            self._persist_session_state(session, context, result)
            return result

        # For proceed/fallback_generic/preselected, verify slot completeness.
        target_key = context.top.bundle_key if context.top is not None else "unknown"
        missing_field, question = await self._replier.build_clarification(
            turn_request.session_id,
            context.extracted,
            target_key,
            history=turn_request.history,
        )
        if missing_field is not None:
            result = self._awaiting_input_response(question, context)
            self._persist_session_state(session, context, result)
            return result

        if not session.confirmed:
            suggestion = context.top
            if suggestion is None:
                question = (
                    "Could you tell me a bit more about what you're looking to "
                    "manage? That'll help me configure this the right way for "
                    "your team."
                )
                result = self._awaiting_input_response(question, context)
                self._persist_session_state(session, context, result)
                return result

            message = await self._replier.build_bundle_suggestion(
                turn_request.session_id,
                suggestion,
                context.slots,
            )
            if status == "fallback_generic":
                message = (
                    "I want to make sure this is set up right for you — could you share "
                    "a bit more about your team's focus? In the meantime, here's what "
                    "I've put together based on what you've shared:\n\n"
                    f"{message}"
                )
            result = self._pending_confirmation_response(message, context)
            self._persist_session_state(session, context, result)
            return result

        result = self._ready_for_preview_response(context, preview_type="confirmed")
        self._persist_session_state(session, context, result)
        return result

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
            session=cast(Session | None, kwargs.get("session")),
            confirmed=cast(bool, kwargs.get("confirmed", False)),
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

    @staticmethod
    def _resolve_session(request: ConversationTurnRequest) -> Session:
        if request.session is not None:
            return request.session
        # Backward-compatible synthetic session for tests/callers that still use
        # explicit fields instead of passing the full Session object.
        return Session(
            session_id=request.session_id,
            confirmed=request.confirmed,
            accumulated_extraction=request.accumulated_extraction,
            preselected_bundle_key=request.preselected_bundle_key,
            preselected_intent=request.options.preselected_intent,
        )

    async def _resolve_summary(
        self,
        request: ConversationTurnRequest,
        session: Session,
    ) -> str:
        if request.options.summary:
            return request.options.summary
        summary_history = request.history[:-1] if request.history else []
        return await self._interpreter.summarize_history(
            request.session_id,
            summary_history,
            session.accumulated_extraction,
        )

    async def _resolve_turn_context(
        self,
        request: ConversationTurnRequest,
        session: Session,
        summary_for_turn: str,
    ) -> _TurnContext:
        interpreter_request = InterpreterRequest(
            session_id=request.session_id,
            user_message=request.user_message,
            history=request.history,
            accumulated_extraction=session.accumulated_extraction,
            summary=summary_for_turn,
            preselected_intent=session.preselected_intent,
        )

        preselected_bundle_key = session.preselected_bundle_key
        if preselected_bundle_key is not None:
            extracted = await self._interpreter.extract_only(interpreter_request)
            classification = self._mock_preselected_classification(
                request.session_id,
                preselected_bundle_key,
            )
        else:
            extracted, classification = await self._interpreter.interpret(
                interpreter_request
            )
            top_bundle = self._interpreter.top_bundle(classification)
            if classification.selected_bundle is None and top_bundle is not None:
                classification = classification.model_copy(
                    update={"selected_bundle": top_bundle}
                )

        top = classification.selected_bundle
        extracted.missing_fields = self._missing_field_detector.compute(
            extracted,
            top.bundle_key if top is not None else None,
        )

        classification = self._fallback_handler.apply(
            classification=classification,
            extracted=extracted,
            clarification_turn_count=session.clarification_turn_count,
        )

        recommendation = self._recommendation_service.recommend(
            classification=classification,
            extracted=extracted,
            preselected_bundle_key=preselected_bundle_key,
        )

        slots = extracted.to_extracted_info().slots
        top = recommendation.primary_bundle or classification.selected_bundle
        return _TurnContext(
            extracted=extracted,
            classification=classification,
            recommendation=recommendation,
            top=top,
            slots=slots,
        )

    def _mock_preselected_classification(
        self,
        session_id: str,
        preselected_bundle_key: str,
    ) -> ClassificationResult:
        suggestion = BundleSuggestion(
            bundle_key=preselected_bundle_key,
            display_name=preselected_bundle_key,
            confidence=1.0,
            reasoning="Pre-selected by user",
            matched_signals=[],
        )
        return ClassificationResult(
            session_id=session_id,
            selected_bundle=suggestion,
            ranked_candidates=[suggestion],
            confidence_status="proceed",
            top_confidence=1.0,
            score_gap=1.0,
            missing_context=[],
            reasoning="Bundle pre-selected by user",
        )

    async def _build_awaiting_question(
        self,
        request: ConversationTurnRequest,
        context: _TurnContext,
    ) -> str:
        status = context.classification.confidence_status
        if status == "suggest_alternatives":
            top_display = context.top.display_name if context.top is not None else ""
            return await self._replier.build_bundle_verification_question(
                request.session_id,
                top_display,
                context.slots,
                history=request.history,
            )

        target_key = context.top.bundle_key if context.top is not None else "unknown"
        _, question = await self._replier.build_clarification(
            request.session_id,
            context.extracted,
            target_key,
            history=request.history,
        )
        return question

    def _build_early_preview_response(
        self,
        context: _TurnContext,
        session_logger: LoggerAdapter[Any],
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
        if context.recommendation.primary_bundle is not None:
            return context.recommendation.primary_bundle.bundle_key
        if context.classification.selected_bundle is not None:
            return context.classification.selected_bundle.bundle_key
        if context.classification.ranked_candidates:
            return context.classification.ranked_candidates[0].bundle_key
        return _FORCE_PREVIEW_FALLBACK_BUNDLE

    def _persist_session_state(
        self,
        session: Session,
        context: _TurnContext,
        result: _FlowResult,
    ) -> None:
        session.accumulated_extraction = context.extracted
        session.latest_classification = context.classification
        session.latest_recommendation = context.recommendation

        if context.recommendation.primary_bundle is not None:
            session.selected_bundle_key = (
                context.recommendation.primary_bundle.bundle_key
            )

        if result.get("status") == "awaiting_input":
            session.clarification_turn_count += 1

    def _awaiting_input_response(
        self,
        question: str,
        context: _TurnContext,
    ) -> _FlowResult:
        return {
            "status": "awaiting_input",
            "question": question,
            "extracted": context.extracted,
            "classification": context.classification,
            "recommendation": context.recommendation,
            "slots": context.slots,
            # Temporary migration shim removed - use classification directly
        }

    def _pending_confirmation_response(
        self,
        message: str,
        context: _TurnContext,
    ) -> _FlowResult:
        bundle_key = context.top.bundle_key if context.top is not None else None
        return {
            "status": "pending_confirmation",
            "message": message,
            "bundle_key": bundle_key,
            "extracted": context.extracted,
            "classification": context.classification,
            "recommendation": context.recommendation,
            "slots": context.slots,
            # Temporary migration shim removed - use classification directly
        }

    def _ready_for_preview_response(
        self,
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
            "classification": context.classification,
            "recommendation": context.recommendation,
            "slots": context.slots,
            "warning": warning,
            "preview_type": preview_type,
        }
