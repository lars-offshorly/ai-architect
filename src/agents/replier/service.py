from __future__ import annotations

from langchain_openai import ChatOpenAI

from core.config import get_settings
from core.logging import get_logger, get_session_logger
from domain.enums.missing_field_type import MissingFieldType
from domain.models.bundle import BundleSuggestion
from domain.models.extracted_info import ExtractedInfo

from .clarification import (
    detect_missing_fields,
    generate_clarification_question,
    is_critical,
)
from .prompts import BUNDLE_SUGGESTION_SYSTEM_PROMPT

from langchain_core.messages import HumanMessage, SystemMessage

logger = get_logger(__name__)


class ReplierService:
    def __init__(self) -> None:
        settings = get_settings()
        self._model = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            temperature=settings.CONVERSATIONAL_TEMPERATURE,
        )

    async def build_clarification(
        self,
        session_id: str,
        extracted: ExtractedInfo,
        required_slots: list[str],
        bundle_key: str,
    ) -> tuple[MissingFieldType | None, str]:
        session_logger = get_session_logger(__name__, session_id)
        missing = detect_missing_fields(extracted, required_slots)

        critical = [f for f in missing if is_critical(f)]
        target = critical[0] if critical else (missing[0] if missing else None)

        if target is None:
            session_logger.info("No missing fields detected")
            return None, ""

        question = await generate_clarification_question(
            self._model, target, bundle_key, extracted.slots
        )
        session_logger.info("Clarification needed for field=%s", target.value)
        return target, question

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
                            f"Recommended workspace: {suggestion.display_name} ({suggestion.bundle_key})\n"
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
