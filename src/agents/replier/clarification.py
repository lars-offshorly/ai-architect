from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from catalog.bundle_catalog import BundleVariantDefinition
from core.logging import get_logger
from domain.enums.missing_field_type import MissingFieldType
from domain.models.conversation import ConversationMessage

from .prompts import CLARIFICATION_SYSTEM_PROMPT

logger = get_logger(__name__)

_CRITICAL_FIELDS: frozenset[MissingFieldType] = frozenset(
    {
        MissingFieldType.PRIMARY_USE_CASE,
        MissingFieldType.ENTITY_TYPE,
        MissingFieldType.WORKFLOW_TYPE,
        MissingFieldType.BUNDLE_VARIANT,
    }
)


def is_critical(field: MissingFieldType) -> bool:
    return field in _CRITICAL_FIELDS


async def generate_clarification_question(
    model: ChatOpenAI,
    missing_field: MissingFieldType,
    bundle_key: str,
    slots: dict[str, object],
    variants: list[BundleVariantDefinition] | None = None,
    history: list[ConversationMessage] | None = None,
) -> str:
    # Bundle-variant clarification is deterministic: we enumerate the
    # declared variants verbatim so the user sees the exact set the system
    # can pick from. No LLM call needed.
    if missing_field == MissingFieldType.BUNDLE_VARIANT:
        return build_bundle_variant_question(bundle_key, variants or [])

    recent = (history or [])[-6:]
    history_text = "\n".join(f"{m.role}: {m.content}" for m in recent)
    context = f"Context gathered so far: {slots}\nStill need: {missing_field.value.replace('_', ' ')}"
    if history_text:
        context = f"Recent conversation:\n{history_text}\n\n{context}"

    try:
        response = await model.ainvoke(
            [
                SystemMessage(content=CLARIFICATION_SYSTEM_PROMPT),
                HumanMessage(content=context),
            ]
        )
        question = str(response.content).strip()
        return question or _fallback_question(missing_field)
    except (RuntimeError, ValueError, TypeError) as exc:
        logger.error("Clarification generation failed: %s", exc)
        return _fallback_question(missing_field)


def build_bundle_variant_question(
    bundle_key: str,
    variants: list[BundleVariantDefinition],
) -> str:
    """Return a deterministic clarification question listing every variant."""
    if not variants:
        return (
            f"Could you share a bit more about how your team will use the "
            f"{bundle_key.replace('_', ' ')} workspace?"
        )
    labels = [
        (v.clarification_label or v.display_name or v.key).strip() for v in variants
    ]
    labels = [label for label in labels if label]
    if len(labels) == 1:
        return f"Should I set this up for {labels[0]}?"
    if len(labels) == 2:
        joined = f"{labels[0]} or {labels[1]}"
    else:
        joined = ", ".join(labels[:-1]) + f", or {labels[-1]}"
    return f"Which best describes how you'll use this workspace: {joined}?"


def _fallback_question(field: MissingFieldType) -> str:
    return f"Could you share your {field.value.replace('_', ' ')}?"
