from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from catalog.bundle_catalog import BundleCatalog
from core.config import get_settings
from core.logging import get_logger, get_session_logger
from domain.enums.missing_field_type import MissingFieldType
from domain.models.bundle import BundleSuggestion
from domain.models.conversation import ConversationMessage
from domain.models.extraction_result import ExtractionResult

from .clarification import (
    generate_clarification_question,
    is_critical,
)
from .prompts import BUNDLE_SUGGESTION_SYSTEM_PROMPT, BUNDLE_VERIFICATION_SYSTEM_PROMPT

logger = get_logger(__name__)


class ReplierService:
    def __init__(self, catalog: BundleCatalog | None = None) -> None:
        settings = get_settings()
        self._model = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            temperature=settings.CONVERSATIONAL_TEMPERATURE,
            api_key=settings.OPENAI_API_KEY,
        )
        self._catalog = catalog

    async def build_clarification(
        self,
        session_id: str,
        extracted: ExtractionResult,
        bundle_key: str,
        history: list[ConversationMessage] | None = None,
    ) -> tuple[MissingFieldType | None, str]:
        session_logger = get_session_logger(__name__, session_id)
        missing = extracted.missing_fields

        critical = [f for f in missing if is_critical(f)]
        target = critical[0] if critical else (missing[0] if missing else None)

        if target is None:
            session_logger.info("No missing fields detected")
            return None, ""

        slots = extracted.to_extracted_info().slots
        variants = self._catalog.get_variants(bundle_key) if self._catalog else None
        question = await generate_clarification_question(
            self._model,
            target,
            bundle_key,
            slots,
            variants=variants,
            history=history,
        )
        session_logger.info("Clarification needed for field=%s", target.value)
        return target, question

    async def build_bundle_verification_question(
        self,
        session_id: str,
        display_name: str,
        slots: dict[str, object],
        history: list[ConversationMessage] | None = None,
    ) -> str:
        session_logger = get_session_logger(__name__, session_id)
        recent = (history or [])[-6:]
        history_text = "\n".join(f"{m.role}: {m.content}" for m in recent)
        context = f"Workspace category: {display_name}\nContext gathered so far: {slots}"
        if history_text:
            context = f"Recent conversation:\n{history_text}\n\n{context}"
        try:
            response = await self._model.ainvoke(
                [
                    SystemMessage(content=BUNDLE_VERIFICATION_SYSTEM_PROMPT),
                    HumanMessage(content=context),
                ]
            )
            question = str(response.content).strip()
        except (RuntimeError, ValueError, TypeError) as exc:
            session_logger.error(
                "Bundle verification question generation failed: %s", exc
            )
            question = (
                "Could you tell me a bit more about your team — "
                "like how many people are involved and how you currently manage things?"
            )
        return question

    async def build_bundle_suggestion(
        self,
        session_id: str,
        suggestion: BundleSuggestion,
        slots: dict[str, object],
    ) -> str:
        session_logger = get_session_logger(__name__, session_id)
        try:
            response = await self._model.ainvoke(
                [
                    SystemMessage(content=BUNDLE_SUGGESTION_SYSTEM_PROMPT),
                    HumanMessage(
                        content=(
                            f"Workspace category: {suggestion.display_name}\n"
                            f"What we know about the user: {slots}"
                        )
                    ),
                ]
            )
            message = str(response.content).strip()
        except (RuntimeError, ValueError, TypeError) as exc:
            session_logger.error("Bundle suggestion generation failed: %s", exc)
            message = f"I recommend {suggestion.display_name}. Does this look right?"

        return message
