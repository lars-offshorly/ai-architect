from __future__ import annotations

# pylint: disable=too-few-public-methods
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from core.logging import get_logger
from domain.models.conversation import ConversationMessage, ConversationSummary
from domain.models.extraction_result import ExtractionResult

from .prompts import SUMMARIZATION_SYSTEM_PROMPT

logger = get_logger(__name__)


def _format_messages(messages: list[ConversationMessage]) -> str:
    lines: list[str] = []
    for msg in messages:
        prefix = "User" if msg.role == "user" else "Assistant"
        lines.append(f"{prefix}: {msg.content}")
    return "\n".join(lines)


def _format_extracted_context(extracted: ExtractionResult) -> str:
    cs = extracted.classification_signals
    ps = extracted.personalization_signals
    parts: list[str] = []
    if cs.keywords:
        parts.append(f"Known keywords: {', '.join(cs.keywords)}")
    if cs.entities:
        parts.append(f"Known entities: {', '.join(cs.entities)}")
    if cs.intents:
        parts.append(f"Known intents: {', '.join(cs.intents)}")
    if cs.workflow_hints:
        parts.append(f"Workflow hints: {', '.join(cs.workflow_hints)}")
    if ps.company_name:
        parts.append(f"Company: {ps.company_name}")
    return "\n".join(parts)


class Summarizer:
    def __init__(self, model: ChatOpenAI) -> None:
        self._model = model

    async def summarize(
        self,
        session_id: str,
        messages: list[ConversationMessage],
        extracted: ExtractionResult | None = None,
    ) -> ConversationSummary:
        if not messages:
            return ConversationSummary(
                session_id=session_id,
                summary_text="",
                message_count=0,
            )

        conversation_text = _format_messages(messages)
        if extracted is not None:
            extracted_context = _format_extracted_context(extracted)
            if extracted_context:
                conversation_text = (
                    f"Already extracted signals:\n{extracted_context}\n\n"
                    f"Conversation:\n{conversation_text}"
                )
        try:
            response = await self._model.ainvoke(
                [
                    SystemMessage(content=SUMMARIZATION_SYSTEM_PROMPT),
                    HumanMessage(content=conversation_text),
                ]
            )
            summary_text = str(response.content).strip()
        except (RuntimeError, ValueError, TypeError) as exc:
            logger.error("Summarization failed for session=%s: %s", session_id, exc)
            summary_text = ""

        return ConversationSummary(
            session_id=session_id,
            summary_text=summary_text,
            message_count=len(messages),
        )
