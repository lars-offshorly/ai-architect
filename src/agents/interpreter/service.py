from __future__ import annotations

from langchain_openai import ChatOpenAI

from catalog.bundle_catalog import BundleCatalog
from core.logging import get_logger, get_session_logger
from domain.models.bundle import BundleSuggestion
from domain.models.classification_result import ClassificationResult
from domain.models.conversation import ConversationMessage
from domain.models.extraction_result import ExtractionResult
from domain.models.interpreter_request import InterpreterRequest
from domain.services.registry_facade import RegistryFacade

from .classifier import Classifier
from .extractor import Extractor
from .signal_accumulator import SignalAccumulator
from .summarizer import Summarizer

logger = get_logger(__name__)


def _build_catalog_context(bundle_keys: list[str]) -> str:
    return "\n".join(f"- {key}" for key in bundle_keys)


class InterpreterService:
    def __init__(
        self,
        bundle_keys: list[str],
        catalog: BundleCatalog | None = None,
        registry_facade: RegistryFacade | None = None,
        model: ChatOpenAI | None = None,
        summarizer_model: ChatOpenAI | None = None,
    ) -> None:
        self._bundle_keys = bundle_keys
        self._registry_facade = registry_facade
        self._extractor = Extractor(model) if model else None
        self._classifier = (
            Classifier(model, _build_catalog_context(bundle_keys), catalog)
            if model and catalog is not None
            else None
        )
        self._summarizer = Summarizer(summarizer_model) if summarizer_model else None

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

        if not self._extractor:
            # Deterministic stub for testing/CI when LLMs are disabled
            extracted = request.accumulated_extraction or ExtractionResult(
                session_id=request.session_id
            )
            if self._registry_facade is not None:
                suggested = self._registry_facade.resolve_bundle(
                    session_id=request.session_id,
                    user_message=request.user_message,
                    extracted=extracted,
                )
            else:
                default_bundle_key = "generic"
                selected_bundle = BundleSuggestion(
                    bundle_key=default_bundle_key,
                    display_name="Custom Workspace",
                    confidence=1.0,
                    reasoning="Stubbed selection (LLM disabled)",
                )
                suggested = ClassificationResult(
                    session_id=request.session_id,
                    selected_bundle=selected_bundle,
                    ranked_candidates=[selected_bundle],
                    confidence_status="proceed",
                    top_confidence=1.0,
                    reasoning="Deterministic stub",
                )
            return extracted, suggested

        current = await self._extractor.extract(
            request.session_id,
            request.user_message,
            history=request.history,
            summary=request.summary,
        )
        extracted = SignalAccumulator.merge(request.accumulated_extraction, current)
        self._inject_preselected_intent(extracted, request.preselected_intent)

        if self._registry_facade is not None:
            suggested = self._registry_facade.resolve_bundle(
                session_id=request.session_id,
                user_message=request.user_message,
                extracted=extracted,
            )
        elif self._classifier is not None:
            suggested = await self._classifier.classify(
                request.session_id,
                request.user_message,
                self._bundle_keys,
                extracted=extracted,
                preselected_intent=request.preselected_intent,
            )
        else:
            suggested = ClassificationResult(
                session_id=request.session_id,
                confidence_status="fallback_generic",
                reasoning="No classifier available",
            )

        session_logger.info(
            "Interpreter complete: top_bundle=%s",
            (
                suggested.selected_bundle.bundle_key
                if suggested.selected_bundle is not None
                else None
            ),
        )
        return extracted, suggested

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
