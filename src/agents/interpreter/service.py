from __future__ import annotations

from langchain_openai import ChatOpenAI

from catalog.bundle_catalog import BundleCatalog
from core.config import get_settings
from core.logging import get_logger, get_session_logger
from domain.models.bundle import BundleSuggestion, SuggestedBundles
from domain.models.conversation import ConversationMessage
from domain.models.extraction_result import ExtractionResult
from domain.models.interpreter_request import InterpreterRequest

from .classifier import Classifier
from .extractor import Extractor
from .signal_accumulator import SignalAccumulator
from .summarizer import Summarizer

logger = get_logger(__name__)


def _build_catalog_context(bundle_keys: list[str]) -> str:
    return "\n".join(f"- {key}" for key in bundle_keys)


class InterpreterService:
    def __init__(self, bundle_keys: list[str], catalog: BundleCatalog) -> None:
        settings = get_settings()
        model = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            temperature=settings.CLASSIFIER_TEMPERATURE,
        )
        catalog_context = _build_catalog_context(bundle_keys)
        self._extractor = Extractor(model, catalog)
        self._classifier = Classifier(model, catalog_context, catalog)
        self._summarizer = Summarizer(
            ChatOpenAI(
                model=settings.OPENAI_MODEL,
                temperature=settings.CONVERSATIONAL_TEMPERATURE,
            )
        )
        self._bundle_keys = bundle_keys
        self._threshold = settings.CONFIDENCE_THRESHOLD

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
    ) -> tuple[ExtractionResult, SuggestedBundles]:
        session_logger = get_session_logger(__name__, request.session_id)
        session_logger.info("Running interpreter")

        current = await self._extractor.extract(
            request.session_id,
            request.user_message,
            history=request.history,
            summary=request.summary,
        )
        extracted = SignalAccumulator.merge(request.accumulated_extraction, current)
        self._inject_preselected_intent(extracted, request.preselected_intent)

        suggested = await self._classifier.classify(
            request.session_id,
            request.user_message,
            self._bundle_keys,
            preselected_intent=request.preselected_intent,
        )
        session_logger.info(
            "Interpreter complete: top_bundle=%s", suggested.top_bundle_key
        )
        return extracted, suggested

    def top_bundle(self, suggested: SuggestedBundles) -> BundleSuggestion | None:
        return self._classifier.top_suggestion(suggested, self._threshold)

    async def summarize_history(
        self,
        session_id: str,
        history: list[ConversationMessage],
        extracted: ExtractionResult | None = None,
    ) -> str:
        summary = await self._summarizer.summarize(
            session_id, history, extracted=extracted
        )
        return summary.summary_text
