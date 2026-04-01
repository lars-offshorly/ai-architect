from __future__ import annotations

import re

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.types import Command

from catalog import BundleCatalog
from core import get_openai_chat_model, get_session_logger, get_settings

from ..states import OnboardingIntents, OnboardingState

CATALOG = BundleCatalog()
SYSTEM_PROMPT = (
    "Extract onboarding intent from the user's message about setting up their team workspace.\n"
    "Determine:\n"
    "- entity_type: 'people' for HR/team management, 'work' for projects/tasks, 'asset' for equipment/physical items\n"
    "- bundle: best matching workspace type from the catalog (null if genuinely unclear)\n"
    "- industry_hint: user's industry or domain (e.g. 'marketing_agency', 'healthcare', 'logistics')\n"
    "- confidence: 0.0-1.0 confidence in bundle selection\n"
    "- raw_intent: one-sentence summary of what they want to manage\n"
    "Prefer a specific bundle over null when context gives reasonable signal."
)


_TEAM_SIZE_RE = re.compile(
    r"\b(\d+)[- ](?:person|people|employee|employees|staff|member|members|strong)\b"
    r"|\b(?:team|org|company|organization|firm)\s+of\s+(\d+)\b"
    r"|\bwe\s+(?:are|have)\s+(\d+)\s+(?:people|employees|staff)\b"
    r"|\bi\s+(?:run|have|manage)\s+(?:a\s+)?(\d+)[- ](?:person|people|employee|employees|member)\b",
    re.IGNORECASE,
)


def _latest_user_message(messages: list[BaseMessage]) -> str:
    for message in reversed(messages):
        if isinstance(message, HumanMessage) and isinstance(message.content, str):
            return message.content.strip()
    return ""


def _extract_team_size(message: str) -> int | None:
    match = _TEAM_SIZE_RE.search(message)
    if not match:
        return None
    for group in match.groups():
        if group is not None:
            return int(group)
    return None


def _catalog_context() -> str:
    entries = [
        f"- {bundle.bundle_key}: {bundle.description}" for bundle in CATALOG.list_all()
    ]
    return "\n".join(entries)


def _coerce_intents(payload: object) -> OnboardingIntents:
    if isinstance(payload, OnboardingIntents):
        return payload
    if isinstance(payload, dict):
        return OnboardingIntents.model_validate(payload)
    raise TypeError("Invalid onboarding intent payload type.")


async def intent_extraction(state: OnboardingState) -> Command:
    session_id = state.get("session_id", "")
    session_logger = get_session_logger(__name__, session_id)
    user_message = _latest_user_message(state.get("messages", []))
    try:
        settings = get_settings()
        model = get_openai_chat_model(temperature=settings.CLASSIFIER_TEMPERATURE)
        structured = model.with_structured_output(OnboardingIntents)
        result = await structured.ainvoke(
            [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(
                    content=(
                        f"Bundles:\n{_catalog_context()}\n\n"
                        f"User message:\n{user_message}"
                    ),
                ),
            ],
        )
        intents = _coerce_intents(result)
    except (RuntimeError, TypeError, ValueError) as exc:
        session_logger.error("Intent extraction failed: %s", exc)
        return Command(goto="clarification")

    slots = dict(state.get("slots", {}))
    if intents.industry_hint and "industry_hint" not in slots:
        slots["industry_hint"] = intents.industry_hint
    if intents.raw_intent and "primary_use_case" not in slots:
        slots["primary_use_case"] = intents.raw_intent
    if "team_size" not in slots:
        extracted_size = _extract_team_size(user_message)
        if extracted_size is not None:
            slots["team_size"] = extracted_size

    conf_pct = f"{intents.confidence:.0%}" if intents.confidence is not None else "?"
    industry = intents.industry_hint or "—"
    step = (
        f"Intent: **{intents.entity_type}** entity | "
        f"Industry: {industry} | "
        f"Intent: _{intents.raw_intent}_"
    )

    if intents.bundle and CATALOG.get(intents.bundle):
        session_logger.info("Intent extraction selected bundle=%s", intents.bundle)
        bundle_step = f"Bundle detected: **{intents.bundle}** ({conf_pct} confidence)"
        return Command(
            goto="slot_filler",
            update={
                "onboarding_intents": intents,
                "slots": slots,
                "thinking_trace": [step, bundle_step],
            },
        )

    session_logger.warning("Intent extraction could not determine a valid bundle")
    bundle_step = f"Bundle unclear ({conf_pct} confidence) — asking for more context"
    return Command(
        goto="clarification",
        update={
            "onboarding_intents": intents,
            "slots": slots,
            "thinking_trace": [step, bundle_step],
        },
    )
