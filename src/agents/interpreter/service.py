from __future__ import annotations

import time

from langchain_openai import ChatOpenAI

from core.logging import get_logger, get_session_logger
from domain.models.bundle import BundleSuggestion
from domain.models.classification_result import ClassificationResult
from domain.models.conversation import ConversationMessage
from domain.models.extraction_result import ExtractionResult
from domain.models.interpreter_request import InterpreterRequest
from domain.services.registry_facade import RegistryFacade

from .extractor import Extractor
from .llm_industry_classifier import IndustryChoice, LLMIndustryClassifier
from .signal_accumulator import SignalAccumulator
from .summarizer import Summarizer

logger = get_logger(__name__)

_GENERIC_BUNDLE_KEY = "generic"
_GENERIC_DISPLAY_NAME = "Custom Workspace"


class InterpreterService:
    def __init__(
        self,
        bundle_keys: list[str],
        registry_facade: RegistryFacade | None = None,
        model: ChatOpenAI | None = None,
        summarizer_model: ChatOpenAI | None = None,
        llm_industry_classifier: LLMIndustryClassifier | None = None,
    ) -> None:
        self._bundle_keys = bundle_keys
        self._registry_facade = registry_facade
        self._extractor = Extractor(model) if model else None
        self._summarizer = Summarizer(summarizer_model) if summarizer_model else None
        self._llm_industry_classifier = llm_industry_classifier

    @staticmethod
    def _inject_preselected_intent(
        extracted: ExtractionResult, preselected_intent: str | None
    ) -> None:
        if (
            preselected_intent
            and preselected_intent not in extracted.classification_signals.intents
        ):
            extracted.classification_signals.intents.insert(0, preselected_intent)

    async def extract_only(self, request: InterpreterRequest) -> ExtractionResult:
        """Run extraction and signal accumulation without calling the LLM classifier.

        Used when the bundle is already known (preselected path) so the classifier
        round-trip cost and latency can be avoided entirely.
        """
        if not self._extractor:
            return request.accumulated_extraction or ExtractionResult(
                session_id=request.session_id
            )

        current = await self._extractor.extract(
            request.session_id,
            request.user_message,
            history=request.history,
            summary=request.summary,
        )
        extracted = SignalAccumulator.merge(request.accumulated_extraction, current)
        self._inject_preselected_intent(extracted, request.preselected_intent)
        return extracted

    async def interpret(
        self, request: InterpreterRequest
    ) -> tuple[ExtractionResult, ClassificationResult]:
        session_logger = get_session_logger(__name__, request.session_id)
        session_logger.info("Running interpreter")

        t0 = time.perf_counter()
        if not self._extractor:
            # Deterministic stub for testing/CI when LLMs are disabled
            extracted = request.accumulated_extraction or ExtractionResult(
                session_id=request.session_id
            )
        else:
            current = await self._extractor.extract(
                request.session_id,
                request.user_message,
                history=request.history,
                summary=request.summary,
            )
            extracted = SignalAccumulator.merge(request.accumulated_extraction, current)
            self._inject_preselected_intent(extracted, request.preselected_intent)
        t1 = time.perf_counter()

        suggested = await self._resolve_classification(request, extracted)
        t2 = time.perf_counter()

        session_logger.info(
            (
                "Interpreter complete: top_bundle=%s extract_ms=%.1f "
                "classify_ms=%.1f total_ms=%.1f"
            ),
            (
                suggested.selected_bundle.bundle_key
                if suggested.selected_bundle is not None
                else None
            ),
            (t1 - t0) * 1000.0,
            (t2 - t1) * 1000.0,
            (t2 - t0) * 1000.0,
        )
        return extracted, suggested

    async def _resolve_classification(
        self,
        request: InterpreterRequest,
        extracted: ExtractionResult,
    ) -> ClassificationResult:
        """Run the 3-stage bundle resolution: alias → LLM → generic."""
        if self._registry_facade is None:
            return self._generic_fallback(
                request.session_id, reason="No canonical registry available"
            )

        # Stage 1: deterministic alias resolver.
        stage1 = self._registry_facade.resolve_bundle(
            session_id=request.session_id,
            user_message=request.user_message,
            extracted=extracted,
        )
        if stage1 is not None and stage1.selected_bundle is not None:
            get_session_logger(__name__, request.session_id).info(
                "Classification stage=alias_resolver"
            )
            return stage1

        # Stage 2: LLM industry classifier (only if available).
        if self._llm_industry_classifier is not None:
            stage2_start = time.perf_counter()
            choice = await self._llm_industry_classifier.classify(
                session_id=request.session_id,
                user_message=request.user_message,
                extracted=extracted,
            )
            get_session_logger(__name__, request.session_id).info(
                "Classification stage=llm_industry elapsed_ms=%.1f",
                (time.perf_counter() - stage2_start) * 1000.0,
            )
            if choice.industry is not None:
                return self._build_classification_from_industry(
                    request.session_id, choice
                )

        # Stage 3: generic fallback.
        return self._generic_fallback(
            request.session_id, reason="No canonical industry matched"
        )

    def _build_classification_from_industry(
        self, session_id: str, choice: IndustryChoice
    ) -> ClassificationResult:
        industry = choice.industry
        if industry is None:
            return self._generic_fallback(
                session_id, reason="LLM classifier returned no industry"
            )
        confidence = float(choice.confidence)
        reasoning = choice.reasoning
        mapping = (
            self._registry_facade.industry_bundle_map()
            if self._registry_facade is not None
            else {}
        )
        spec = mapping.get(industry, {})
        bundle_key = str(spec.get("bundle_key") or _GENERIC_BUNDLE_KEY)

        suggestion = BundleSuggestion(
            bundle_key=bundle_key,
            display_name=bundle_key.replace("_", " ").title(),
            confidence=confidence,
            reasoning=f"LLM matched industry '{industry}': {reasoning}",
            matched_signals=[industry],
        )
        return ClassificationResult(
            session_id=session_id,
            selected_bundle=suggestion,
            ranked_candidates=[suggestion],
            confidence_status="proceed",
            top_confidence=confidence,
            reasoning="LLM canonical industry classifier",
        )

    @staticmethod
    def _generic_fallback(session_id: str, reason: str) -> ClassificationResult:
        suggestion = BundleSuggestion(
            bundle_key=_GENERIC_BUNDLE_KEY,
            display_name=_GENERIC_DISPLAY_NAME,
            confidence=0.45,
            reasoning=reason,
            matched_signals=[],
        )
        return ClassificationResult(
            session_id=session_id,
            selected_bundle=suggestion,
            ranked_candidates=[suggestion],
            confidence_status="fallback_generic",
            top_confidence=suggestion.confidence,
            reasoning=reason,
        )

    def top_bundle(self, suggested: ClassificationResult) -> BundleSuggestion | None:
        return suggested.selected_bundle

    async def summarize_history(
        self,
        session_id: str,
        history: list[ConversationMessage],
        extracted: ExtractionResult | None = None,
    ) -> str:
        if not self._summarizer:
            return ""
        summary = await self._summarizer.summarize(
            session_id, history, extracted=extracted
        )
        return summary.summary_text
