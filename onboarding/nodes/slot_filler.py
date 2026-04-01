from __future__ import annotations

import re

from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.types import Command

from catalog import BundleCatalog
from core import get_session_logger

from ..states import OnboardingState


CATALOG = BundleCatalog()


def _latest_user_message(messages: list[BaseMessage]) -> str:
    for message in reversed(messages):
        if isinstance(message, HumanMessage) and isinstance(message.content, str):
            return message.content.strip()
    return ""


def _coerce_slot_value(slot_key: str, raw_value: str) -> object:
    if slot_key.endswith("_count") or slot_key.endswith("_size"):
        match = re.search(r"\d+", raw_value)
        if match:
            return int(match.group())
    return raw_value


def _is_missing(value: object | None) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False


async def slot_filler(state: OnboardingState) -> Command:
    session_id = state.get("session_id", "")
    session_logger = get_session_logger(__name__, session_id)
    intents = state.get("onboarding_intents")
    if intents is None or not intents.bundle:
        session_logger.warning("Slot filler missing bundle context")
        return Command(goto="clarification")

    slots = dict(state.get("slots", {}))
    clarification_queue = list(state.get("clarification_queue", []))
    latest_answer = _latest_user_message(state.get("messages", []))
    if clarification_queue and latest_answer:
        slot_key = clarification_queue.pop(0)
        slots[slot_key] = _coerce_slot_value(slot_key, latest_answer)

    required_slots = CATALOG.get_required_slots(intents.bundle)
    missing_slots = [slot for slot in required_slots if _is_missing(slots.get(slot))]
    if missing_slots:
        session_logger.info("Missing slots detected: %s", missing_slots)
        step = f"Slots: still need **{', '.join(missing_slots)}**"
        return Command(
            goto="clarification",
            update={"slots": slots, "clarification_queue": missing_slots, "thinking_trace": [step]},
        )

    filled = ", ".join(f"{k}={v}" for k, v in slots.items() if v is not None)
    session_logger.info("All required slots filled for bundle=%s", intents.bundle)
    step = f"Slots complete ✓ ({filled})"
    return Command(
        goto="bundle_confirmer",
        update={"slots": slots, "clarification_queue": [], "thinking_trace": [step]},
    )
