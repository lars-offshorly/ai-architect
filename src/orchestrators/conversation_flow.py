from __future__ import annotations

import inspect
import re
from dataclasses import dataclass, field
from logging import LoggerAdapter
from typing import Any, Protocol, cast

from agents.interpreter.fallback import FallbackHandler
from agents.interpreter.missing_fields import MissingFieldDetector
from core.config import get_settings
from core.logging import get_logger, get_session_logger
from domain.models.bundle import BundleSuggestion
from domain.models.classification_result import ClassificationResult
from domain.models.conversation import ConversationMessage
from domain.models.extraction_result import ExtractionResult
from domain.models.interpreter_request import InterpreterRequest
from domain.models.recommendation_result import RecommendationResult
from domain.models.session import Session
from domain.services.registry_facade import RegistryFacade

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
_WORKFLOW_HINTS: dict[str, tuple[str, ...]] = {
    "ticketing": ("ticket", "tickets", "ticketing", "queue", "queues"),
    "project_mgmt": ("project", "projects", "task", "tasks"),
    "hr_management": ("hr", "recruitment", "employee", "employees", "hiring"),
}
_INDUSTRY_LABELS: dict[str, str] = {
    "construction_firm": "construction",
    "bpo_contact_center": "BPO/contact center",
    "hr_recruitment_agency": "HR recruitment",
}


def _contains_term(text: str, term: str) -> bool:
    return re.search(r"\b" + re.escape(term.lower()) + r"\b", text.lower()) is not None


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

    # Compatibility fields kept for existing tests/callers.
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
    selection_context: str = ""


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
        bundle_catalog: object | None = None,
        required_slots_by_bundle: dict[str, list[str]] | None = None,
        registry_facade: RegistryFacade | None = None,
    ) -> None:
        _ = bundle_catalog  # backward-compatible constructor arg
        self._interpreter = interpreter_service
        self._replier = replier_service
        self._missing_field_detector = MissingFieldDetector(
            required_slots_by_bundle or {}
        )
        self._fallback_handler = FallbackHandler(
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
        self._registry_facade = registry_facade

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
        # pylint: disable=too-many-locals
        turn_request = self._coerce_turn_request(request, kwargs)
        session = self._resolve_session(turn_request)
        self._update_session_context(session, turn_request.user_message)
        session_logger = get_session_logger(__name__, turn_request.session_id)

        summary_for_turn = await self._resolve_summary(turn_request, session)
        context = await self._resolve_turn_context(
            turn_request,
            session,
            summary_for_turn,
        )

        ambiguous_industries = self._ambiguous_industries(turn_request.user_message)
        if (
            ambiguous_industries
            and session.company_industry_claim is None
            and not session.confirmed
            and session.preselected_bundle_key is None
        ):
            question = (
                "To tailor this correctly, which best describes your business: "
                "construction, BPO/contact center, or HR recruitment?"
            )
            result = self._awaiting_input_response(question, context)
            self._persist_session_state(session, context, result)
            return result

        if self.should_generate_early_preview(
            turn_request.user_message, turn_request.options.force_preview
        ):
            result = self._build_early_preview_response(context, session_logger)
            self._persist_session_state(session, context, result)
            return result

        if (
            not session.confirmed
            and session.selected_bundle_key is not None
            and _detect_confirmation_intent(turn_request.user_message)
        ):
            session_logger.info(
                "Confirmation intent detected for bundle=%s",
                session.selected_bundle_key,
            )
            session.confirmed = True
            result = self._ready_for_preview_response(context, preview_type="confirmed")

        # Always ask exactly one verification question on the first unconfirmed turn,
        # regardless of confidence, to collect user context and confirm the bundle fit.
        # This runs before all confidence-based branching so every path gets the same
        # smart follow-up on turn 1.
        if (
            session.clarification_turn_count == 0
            and not session.confirmed
            and session.preselected_bundle_key is None
        ):
            question = await self._build_verification_question(turn_request, context)
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
                    "I want to make sure this is set up right for you - "
                    "could you share "
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

    def _industry_mapping(self) -> dict[str, dict[str, Any]]:
        if self._registry_facade is None:
            return {}
        return self._registry_facade.industry_bundle_map()

    def _ambiguous_industries(self, user_message: str) -> list[str]:
        mapping = self._industry_mapping()
        if not mapping:
            return []
        matched: list[str] = []
        lowered = user_message.lower()
        for industry, spec in mapping.items():
            if _contains_term(lowered, industry.lower()):
                matched.append(industry)
                continue
            aliases = spec.get("aliases", [])
            if isinstance(aliases, list) and any(
                isinstance(alias, str) and _contains_term(lowered, alias)
                for alias in aliases
            ):
                matched.append(industry)
        return matched if len(matched) >= 2 else []

    def _update_session_context(self, session: Session, user_message: str) -> None:
        text = user_message.lower()
        mapping = self._industry_mapping()
        for industry, label in _INDUSTRY_LABELS.items():
            if _contains_term(text, industry) or _contains_term(text, label):
                session.company_industry_claim = industry
                bundle_key = mapping.get(industry, {}).get("bundle_key")
                if isinstance(bundle_key, str):
                    session.preselected_bundle_key = bundle_key
                break

        for workflow, hints in _WORKFLOW_HINTS.items():
            if any(_contains_term(text, hint) for hint in hints):
                session.primary_workflow = workflow
                break

        if "internal" in text and "only" in text:
            session.audience_scope = "internal_only"
        elif any(
            _contains_term(text, token)
            for token in ("client", "customer", "subcontractor")
        ):
            session.audience_scope = "external_or_mixed"

        size_match = re.search(
            r"\b(\d{1,4})\s+(?:people|person|users?|employees?|team)\b", text
        )
        if size_match:
            session.inferred_team_size = int(size_match.group(1))

        company_match = re.search(
            (
                r"\b(?:company called|called)\s+([a-z0-9][a-z0-9 '&.-]{1,60}?)"
                r"(?=\s+(?:and|with|that)\b|[.,!?;:]|$)"
            ),
            user_message,
            flags=re.IGNORECASE,
        )
        if company_match:
            session.inferred_company_name = company_match.group(1).strip(" .,!?:;")

        if any(
            _contains_term(text, token)
            for token in ("philippines", "from ph", "manila", "cebu", "davao")
        ):
            session.inferred_region = "PH"

    def _confirmation_summary(self, session: Session, bundle_key: str | None) -> str:
        details: list[str] = []
        industry = session.company_industry_claim
        if industry:
            details.append(f"Industry: {_INDUSTRY_LABELS.get(industry, industry)}")
        workflow = session.primary_workflow
        if workflow:
            details.append(f"Workflow: {workflow.replace('_', ' ')}")
        audience = session.audience_scope
        if audience == "internal_only":
            details.append("Audience: internal teams")
        if not details:
            return ""
        bundle_line = (
            f"Proposed bundle: {bundle_key}"
            if bundle_key
            else "Proposed bundle selected"
        )
        return bundle_line + " | " + " | ".join(details)

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

        recommendation = self._build_recommendation(
            classification=classification,
            preselected_bundle_key=preselected_bundle_key,
        )

        slots = extracted.to_extracted_info().slots
        top = recommendation.primary_bundle or classification.selected_bundle
        selection_context = self._confirmation_summary(
            session,
            top.bundle_key if top is not None else None,
        )
        return _TurnContext(
            extracted=extracted,
            classification=classification,
            recommendation=recommendation,
            top=top,
            slots=slots,
            selection_context=selection_context,
        )

    def _build_recommendation(
        self,
        classification: ClassificationResult,
        preselected_bundle_key: str | None,
    ) -> RecommendationResult:
        """Map ``ClassificationResult`` → ``RecommendationResult``.

        This is the sole owner of recommendation construction. The earlier
        ``BundleRecommendationService`` was removed when the canonical
        registry path landed; the logic now lives inline here.
        """
        selected = classification.selected_bundle

        if preselected_bundle_key:
            if selected is None:
                selected = BundleSuggestion(
                    bundle_key=preselected_bundle_key,
                    display_name=preselected_bundle_key,
                    confidence=1.0,
                    reasoning="Pre-selected by user",
                    matched_signals=[],
                )
            return RecommendationResult(
                session_id=classification.session_id,
                primary_bundle=selected,
                fallback_bundles=[],
                recommendation_status="preselected",
                inferred_modules=self._inferred_modules_for(selected.bundle_key),
                reasoning="Bundle pre-selected by user",
            )

        if classification.confidence_status == "suggest_alternatives":
            fallbacks = classification.ranked_candidates[1:3]
            return RecommendationResult(
                session_id=classification.session_id,
                primary_bundle=selected,
                fallback_bundles=fallbacks,
                recommendation_status="needs_clarification",
                inferred_modules=self._inferred_modules_for(
                    selected.bundle_key if selected is not None else "generic"
                ),
                reasoning="Multiple viable bundles; user choice required",
            )

        if classification.confidence_status == "fallback_generic":
            return RecommendationResult(
                session_id=classification.session_id,
                primary_bundle=selected,
                fallback_bundles=[],
                recommendation_status="fallback_generic",
                inferred_modules=self._inferred_modules_for(
                    selected.bundle_key if selected is not None else "generic"
                ),
                reasoning=classification.reasoning,
            )

        status = (
            "ready"
            if classification.confidence_status == "proceed"
            else "needs_clarification"
        )
        return RecommendationResult(
            session_id=classification.session_id,
            primary_bundle=selected,
            fallback_bundles=[],
            recommendation_status=status,
            inferred_modules=self._inferred_modules_for(
                selected.bundle_key if selected is not None else "generic"
            ),
            reasoning=classification.reasoning or "Need more context from the user",
        )

    def _inferred_modules_for(self, bundle_key: str) -> list[str]:
        if self._registry_facade is not None:
            return self._registry_facade.inferred_modules_for_bundle(bundle_key)
        return []

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
            return await self._build_verification_question(request, context)

        target_key = context.top.bundle_key if context.top is not None else "unknown"
        _, question = await self._replier.build_clarification(
            request.session_id,
            context.extracted,
            target_key,
            history=request.history,
        )
        return question

    async def _build_verification_question(
        self,
        request: ConversationTurnRequest,
        context: _TurnContext,
    ) -> str:
        top_display = context.top.display_name if context.top is not None else ""
        question_or_awaitable = self._replier.build_bundle_verification_question(
            request.session_id,
            top_display,
            context.slots,
            history=request.history,
        )
        if inspect.isawaitable(question_or_awaitable):
            return await question_or_awaitable

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
            "selection_context": context.selection_context,
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
