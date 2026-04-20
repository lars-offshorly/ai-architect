from __future__ import annotations

from langchain_openai import ChatOpenAI

from catalog.bundle_catalog import BundleCatalog
from core.config import get_settings
from core.logging import get_logger, get_session_logger
from domain.enums.missing_field_type import MissingFieldType
from domain.models.bundle import BundleSuggestion
from domain.models.classification_result import ClassificationResult
from domain.models.conversation import ConversationMessage
from domain.models.extraction_result import ExtractionResult
from domain.models.interpreter_request import InterpreterRequest

from .classifier import Classifier
from .extractor import Extractor
from .signal_accumulator import SignalAccumulator
from .summarizer import Summarizer
from .variant_selector import select as select_variant

logger = get_logger(__name__)


def _build_catalog_context(bundle_keys: list[str]) -> str:
    return "\n".join(f"- {key}" for key in bundle_keys)


class InterpreterService:
    def __init__(self, bundle_keys: list[str], catalog: BundleCatalog) -> None:
        settings = get_settings()
        model = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            temperature=settings.CLASSIFIER_TEMPERATURE,
            api_key=settings.OPENAI_API_KEY,
        )
        catalog_context = _build_catalog_context(bundle_keys)
        self._extractor = Extractor(model, catalog)
        self._classifier = Classifier(model, catalog_context, catalog)
        self._summarizer = Summarizer(
            ChatOpenAI(
                model=settings.OPENAI_MODEL,
                temperature=settings.CONVERSATIONAL_TEMPERATURE,
                api_key=settings.OPENAI_API_KEY,
            )
        )
        self._bundle_keys = bundle_keys
        self._catalog = catalog

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
    ) -> tuple[ExtractionResult, ClassificationResult]:
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
            extracted=extracted,
            preselected_intent=request.preselected_intent,
        )

        self._apply_variant_selection(
            request.session_id,
            request.user_message,
            extracted,
            suggested,
        )

        session_logger.info(
            "Interpreter complete: top_bundle=%s variant=%s",
            (
                suggested.selected_bundle.bundle_key
                if suggested.selected_bundle is not None
                else None
            ),
            (
                suggested.selected_bundle.variant_key
                if suggested.selected_bundle is not None
                else None
            ),
        )
        return extracted, suggested

    def _apply_variant_selection(
        self,
        session_id: str,
        user_message: str,
        extracted: ExtractionResult,
        suggested: ClassificationResult,
    ) -> None:
        """Run the deterministic ``VariantSelector`` on the classifier's pick.

        On a confident selection, writes ``variant_key`` /
        ``variant_confidence`` on ``suggested.selected_bundle`` and mirrors
        ``variant_key`` onto ``extracted``. When the selector is ambiguous,
        appends ``MissingFieldType.BUNDLE_VARIANT`` to
        ``extracted.missing_fields`` so the replier can ask a clarification
        question.
        """
        top = suggested.selected_bundle
        if top is None:
            return
        bundle = self._catalog.get(top.bundle_key)
        if bundle is None or not bundle.variants:
            return

        selection = select_variant(
            bundle=bundle,
            extracted=extracted,
            user_message=user_message,
        )

        if selection.variant_key is not None:
            top.variant_key = selection.variant_key
            top.variant_confidence = _normalize_variant_confidence(
                selection.top_score
            )
            extracted.bundle_variant_key = selection.variant_key
            if MissingFieldType.BUNDLE_VARIANT in extracted.missing_fields:
                extracted.missing_fields = [
                    mf
                    for mf in extracted.missing_fields
                    if mf != MissingFieldType.BUNDLE_VARIANT
                ]
            return

        if MissingFieldType.BUNDLE_VARIANT not in extracted.missing_fields:
            extracted.missing_fields.append(MissingFieldType.BUNDLE_VARIANT)
        logger.info(
            "session=%s bundle=%s: variant ambiguous (reason=%s top=%d gap=%d) "
            "→ clarification needed",
            session_id,
            bundle.bundle_key,
            selection.reason,
            selection.top_score,
            selection.score_gap,
        )

    def top_bundle(self, suggested: ClassificationResult) -> BundleSuggestion | None:
        return suggested.selected_bundle

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


def _normalize_variant_confidence(score: int) -> float:
    """Map an integer variant score to a 0.0–1.0 confidence."""
    if score <= 0:
        return 0.0
    # 9 is roughly the cap of a clean 3-keyword + 1-entity + 1-intent match;
    # anything beyond that is treated as saturated.
    saturated = min(score, 9)
    return round(saturated / 9.0, 3)
