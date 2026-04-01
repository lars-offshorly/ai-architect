from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from core.logging import get_logger
from domain.enums.missing_field_type import MissingFieldType

from .prompts import CLARIFICATION_SYSTEM_PROMPT

logger = get_logger(__name__)

_CRITICAL_FIELDS: frozenset[MissingFieldType] = frozenset(
    {
        MissingFieldType.PRIMARY_USE_CASE,
        MissingFieldType.ENTITY_TYPE,
        MissingFieldType.WORKFLOW_TYPE,
    }
)


def is_critical(field: MissingFieldType) -> bool:
    return field in _CRITICAL_FIELDS


async def generate_clarification_question(
    model: ChatOpenAI,
    missing_field: MissingFieldType,
    bundle_key: str,
    slots: dict[str, object],
) -> str:
    try:
        response = await model.ainvoke(
            [
                SystemMessage(content=CLARIFICATION_SYSTEM_PROMPT),
                HumanMessage(
                    content=(
                        f"Workspace type being set up: {bundle_key}\n"
                        f"Already collected: {slots}\n"
                        f"Still need: {missing_field.value.replace('_', ' ')}"
                    )
                ),
            ]
        )
        question = str(response.content).strip()
        return question or _fallback_question(missing_field)
    except (RuntimeError, ValueError, TypeError) as exc:
        logger.error("Clarification generation failed: %s", exc)
        return _fallback_question(missing_field)


def _fallback_question(field: MissingFieldType) -> str:
    return f"Could you share your {field.value.replace('_', ' ')}?"
