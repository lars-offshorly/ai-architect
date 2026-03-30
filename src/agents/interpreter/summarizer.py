from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from core.logging import get_logger
from domain.models.conversation import ConversationMessage, ConversationSummary

from .prompts import SUMMARIZATION_SYSTEM_PROMPT

logger = get_logger(__name__)


def _format_messages(messages: list[ConversationMessage]) -> str:
    lines: list[str] = []
    for msg in messages:
        prefix = "User" if msg.role == "user" else "Assistant"
        lines.append(f"{prefix}: {msg.content}")
    return "\n".join(lines)


class Summarizer:
    def __init__(self, model: ChatOpenAI) -> None:
        self._model = model

    async def summarize(
        self,
        session_id: str,
        messages: list[ConversationMessage],
    ) -> ConversationSummary:
        if not messages:
            return ConversationSummary(
                session_id=session_id,
                summary_text="",
                message_count=0,
            )

        conversation_text = _format_messages(messages)
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
