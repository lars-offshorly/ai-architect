from __future__ import annotations

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.types import Command

from core import get_openai_chat_model, get_session_logger, get_settings

from ..states import OnboardingState, TurnClassification

TURN_ROUTING: dict[str, str] = {
    "new_onboarding": "intent_extraction",
    "clarification_answer": "slot_filler",
    "bundle_confirmation": "bundle_confirmer",
    "bundle_rejection": "slot_filler",
    "out_of_scope": "clarification",
    "harmful": "clarification",
}

SYSTEM_PROMPT = (
    "Classify a user's message in a workspace onboarding conversation.\n"
    "Categories:\n"
    "- new_onboarding: User is describing their team/business situation for the "
    "first time\n"
    "- clarification_answer: User is responding to a specific question "
    "(a detail, number, or short reply)\n"
    "- bundle_confirmation: User agrees to a suggested workspace type "
    "(e.g. 'yes', 'confirm', 'sounds good', 'that works', 'go ahead')\n"
    "- bundle_rejection: User rejects the suggestion or wants something different\n"
    "- out_of_scope: Message is unrelated to workspace setup\n"
    "- harmful: Dangerous or inappropriate content\n"
    "Default to clarification_answer for short, direct responses to previous questions."
)


def _latest_user_message(messages: list[BaseMessage]) -> str:
    for message in reversed(messages):
        if isinstance(message, HumanMessage) and isinstance(message.content, str):
            return message.content.strip()
    return ""


def _coerce_classification(payload: object) -> TurnClassification:
    if isinstance(payload, TurnClassification):
        return payload
    if isinstance(payload, dict):
        return TurnClassification.model_validate(payload)
    raise TypeError("Invalid turn classification payload type.")


async def conversation_classifier(state: OnboardingState) -> Command:
    session_id = state.get("session_id", "")
    session_logger = get_session_logger(__name__, session_id)
    messages = state.get("messages", [])
    user_message = _latest_user_message(messages)
    turn_count = int(state.get("turn_count", 0)) + 1

    if not user_message:
        session_logger.warning("Missing user message for turn classification")
        return Command(goto="clarification", update={"turn_count": turn_count})

    try:
        settings = get_settings()
        model = get_openai_chat_model(temperature=settings.CLASSIFIER_TEMPERATURE)
        structured = model.with_structured_output(TurnClassification)
        result = await structured.ainvoke(
            [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=user_message),
            ],
        )
        classification = _coerce_classification(result)
    except (RuntimeError, TypeError, ValueError) as exc:
        session_logger.error("Turn classification failed: %s", exc)
        step = f"Turn #{turn_count}: classification failed — routing to clarification"
        return Command(
            goto="clarification",
            update={"turn_count": turn_count, "thinking_trace": [step]},
        )

    target_node = TURN_ROUTING.get(classification.turn_type, "clarification")
    session_logger.info("Turn classified as %s", classification.turn_type)
    step = f"Turn #{turn_count}: classified as **{classification.turn_type}**"
    return Command(
        goto=target_node, update={"turn_count": turn_count, "thinking_trace": [step]}
    )
