from __future__ import annotations

from langchain_openai import ChatOpenAI

from core.config import get_settings
from core.logging import get_logger, get_session_logger
from domain.models.bundle import BundleSuggestion, SuggestedBundles
from domain.models.conversation import ConversationMessage
from domain.models.extracted_info import ExtractedInfo

from .classifier import Classifier
from .extractor import Extractor
from .summarizer import Summarizer

logger = get_logger(__name__)


def _build_catalog_context(bundle_keys: list[str]) -> str:
    return "\n".join(f"- {key}" for key in bundle_keys)


def _merge_slots(base: dict[str, object], extracted: ExtractedInfo) -> dict[str, object]:
    merged = dict(base)
    if extracted.company_name and "company_name" not in merged:
        merged["company_name"] = extracted.company_name
    if extracted.industry_hint and "industry_hint" not in merged:
        merged["industry_hint"] = extracted.industry_hint
    if extracted.primary_use_case and "primary_use_case" not in merged:
        merged["primary_use_case"] = extracted.primary_use_case
    return merged


class InterpreterService:
    def __init__(self, bundle_keys: list[str]) -> None:
        settings = get_settings()
        model = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            temperature=settings.CLASSIFIER_TEMPERATURE,
        )
        catalog_context = _build_catalog_context(bundle_keys)
        self._extractor = Extractor(model)
        self._classifier = Classifier(model, catalog_context)
        self._summarizer = Summarizer(
            ChatOpenAI(
                model=settings.OPENAI_MODEL,
                temperature=settings.CONVERSATIONAL_TEMPERATURE,
            )
        )
        self._bundle_keys = bundle_keys
        self._threshold = settings.CONFIDENCE_THRESHOLD

    async def interpret(
        self,
        session_id: str,
        user_message: str,
        existing_slots: dict[str, object],
        history: list[ConversationMessage],
    ) -> tuple[ExtractedInfo, SuggestedBundles]:
        session_logger = get_session_logger(__name__, session_id)
        session_logger.info("Running interpreter")

        extracted = await self._extractor.extract(session_id, user_message)
        merged_slots = _merge_slots(existing_slots, extracted)
        extracted.slots = merged_slots

        suggested = await self._classifier.classify(
            session_id, user_message, self._bundle_keys
        )
        session_logger.info(
            "Interpreter complete: top_bundle=%s", suggested.top_bundle_key
        )
        return extracted, suggested

    def top_bundle(
        self, suggested: SuggestedBundles
    ) -> BundleSuggestion | None:
        return self._classifier.top_suggestion(suggested, self._threshold)

    async def summarize_history(
        self,
        session_id: str,
        history: list[ConversationMessage],
    ) -> str:
        summary = await self._summarizer.summarize(session_id, history)
        return summary.summary_text
