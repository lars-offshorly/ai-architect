from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.runnables.config import var_child_runnable_config
from langgraph.types import Command, interrupt

from core import get_openai_chat_model, get_session_logger, get_settings

from ..states import OnboardingState


SYSTEM_PROMPT = (
    "You are a friendly assistant helping someone configure their team's workspace. "
    "Ask ONE natural, conversational question to learn the missing detail. "
    "Reference what you already know about their situation when relevant. "
    "Be warm and concise — 1-2 sentences max. No bullet lists, no multiple questions, no explanations."
)


def _next_slot(state: OnboardingState) -> str:
    queue = state.get("clarification_queue", [])
    if queue:
        return str(queue[0])
    return "bundle"


def _message_text(payload: object) -> str:
    if isinstance(payload, AIMessage):
        return str(payload.content)
    if isinstance(payload, str):
        return payload
    return ""


def _recent_conversation(state: OnboardingState) -> str:
    messages = state.get("messages", [])
    lines: list[str] = []
    for m in messages[-6:]:
        if isinstance(m, HumanMessage):
            lines.append(f"User: {m.content}")
        elif isinstance(m, AIMessage):
            lines.append(f"Assistant: {m.content}")
    return "\n".join(lines)


async def _generate_question(state: OnboardingState, slot_key: str) -> str:
    settings = get_settings()
    model = get_openai_chat_model(temperature=settings.CONVERSATIONAL_TEMPERATURE)
    slots = dict(state.get("slots", {}))
    intents = state.get("onboarding_intents")
    bundle = intents.bundle if intents else "unknown"
    conversation = _recent_conversation(state)
    try:
        response = await model.ainvoke(
            [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(
                    content=(
                        f"Workspace type being set up: {bundle}\n"
                        f"Already collected: {slots}\n"
                        f"Still need: {slot_key.replace('_', ' ')}\n"
                        f"\nRecent conversation:\n{conversation}"
                    ),
                ),
            ],
        )
    except (RuntimeError, TypeError, ValueError):
        return f"Could you share your {slot_key.replace('_', ' ')}?"

    question = _message_text(response).strip()
    return question or f"Could you share your {slot_key.replace('_', ' ')}?"


async def clarification(state: OnboardingState, config: RunnableConfig) -> Command:
    session_id = state.get("session_id", "")
    session_logger = get_session_logger(__name__, session_id)
    slot_key = _next_slot(state)
    question = await _generate_question(state, slot_key)
    step = f"Asking for: **{slot_key.replace('_', ' ')}**"
    session_logger.info("Issuing clarification question for slot=%s", slot_key)
    token = var_child_runnable_config.set(config)
    try:
        user_reply = interrupt({"question": question, "slot": slot_key})
    finally:
        var_child_runnable_config.reset(token)

    answer = str(user_reply).strip() if user_reply else ""
    return Command(
        goto="conversation_classifier",
        update={"messages": [HumanMessage(content=answer, name="user")], "thinking_trace": [step]},
    )
