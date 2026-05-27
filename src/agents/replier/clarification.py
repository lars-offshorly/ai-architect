from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from agents.interpreter.provisioning_readiness import (
    ProvisioningReadinessResult,
    TenantField,
)
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
    readiness: ProvisioningReadinessResult | None = None,
    known_facts: dict[str, object] | None = None,
) -> str:
    # Bundle-variant clarification is deterministic: we enumerate the
    # declared variants verbatim so the user sees the exact set the system
    # can pick from. No LLM call needed.
    if missing_field == MissingFieldType.BUNDLE_VARIANT:
        return build_bundle_variant_question(bundle_key, variants or [])

    context = _build_clarification_context(
        slots=slots,
        missing_field=missing_field,
        history=history,
        readiness=readiness,
        known_facts=known_facts,
    )

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


def _build_clarification_context(
    slots: dict[str, object],
    missing_field: MissingFieldType,
    history: list[ConversationMessage] | None,
    readiness: ProvisioningReadinessResult | None,
    known_facts: dict[str, object] | None,
) -> str:
    sections: list[str] = []
    history_section = _format_history_section(history)
    if history_section:
        sections.append(history_section)
    facts_section = _format_known_facts_section(known_facts)
    if facts_section:
        sections.append(facts_section)
    sections.append(_format_missing_section(readiness, missing_field))
    if slots:
        sections.append(f"Extracted slots (raw): {slots}")
    return "\n\n".join(sections)


def _format_history_section(history: list[ConversationMessage] | None) -> str:
    recent = (history or [])[-6:]
    if not recent:
        return ""
    history_text = "\n".join(f"{m.role}: {m.content}" for m in recent)
    return f"Recent conversation:\n{history_text}"


def _format_known_facts_section(known_facts: dict[str, object] | None) -> str:
    if not known_facts:
        return ""
    lines = [f"- {key}: {value}" for key, value in known_facts.items() if value]
    if not lines:
        return ""
    return "Known tenant facts:\n" + "\n".join(lines)


def _format_missing_section(
    readiness: ProvisioningReadinessResult | None,
    missing_field: MissingFieldType,
) -> str:
    if readiness is None:
        return f"Still need: {missing_field.value.replace('_', ' ')}"
    missing_required = [f.value for f in readiness.missing_required]
    missing_optional = [f.value for f in readiness.missing_optional]
    if not missing_required and not missing_optional:
        return (
            "Still missing: nothing — return a single confirmation "
            "sentence instead of a question."
        )
    lines: list[str] = []
    if missing_required:
        lines.append("Required (ask these first): " + ", ".join(missing_required))
    if missing_optional:
        lines.append(
            "Optional (only if no required left): " + ", ".join(missing_optional)
        )
    return "Still missing:\n" + "\n".join(lines)


def known_facts_from_readiness(
    readiness: ProvisioningReadinessResult,
    slots: dict[str, object],
) -> dict[str, object]:
    """Build a dict of tenant fields the system already knows.

    Reads only the fields ProvisioningReadiness considers — keeps the LLM
    focused on the v2 manifest surface instead of the full extracted slot dict.
    """
    all_fields = set(TenantField)
    missing = set(readiness.missing_required) | set(readiness.missing_optional)
    known_fields = all_fields - missing
    facts: dict[str, object] = {}
    for field in known_fields:
        value = slots.get(field.value)
        if value:
            facts[field.value] = value
    return facts


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


# Deterministic prompts for tenant-header fields. Used when no
# ``MissingFieldType`` is left to ask about but ``ProvisioningReadiness``
# still flags a required tenant field as unknown.
_TENANT_FIELD_QUESTIONS: dict[TenantField, str] = {
    TenantField.INDUSTRY: (
        "To set this up correctly, which best describes your business: "
        "construction, BPO/contact center, or HR recruitment?"
    ),
    TenantField.COMPANY_NAME: "What's your company or team name?",
    TenantField.SIZE_BAND: "Roughly how many people are on your team?",
    TenantField.PRIMARY_REGION: "Where is your team primarily based?",
}


def question_for_tenant_field(field: TenantField) -> str:
    """Return a deterministic prompt for a missing tenant-header field."""
    return _TENANT_FIELD_QUESTIONS.get(
        field, f"Could you share your {field.value.replace('_', ' ')}?"
    )
