from __future__ import annotations

# pylint: disable=duplicate-code
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.runnables.config import var_child_runnable_config
from langgraph.types import Command, interrupt

from catalog import BundleCatalog
from core import get_openai_chat_model, get_session_logger, get_settings

from ..states import OnboardingState

CATALOG = BundleCatalog()
SYSTEM_PROMPT = (
    "You are a friendly workspace setup assistant who just gathered information "
    "from the user. "
    "Write a warm, personalized confirmation message (2-3 sentences) that: "
    "briefly reflects what you learned about their situation, "
    "recommends the workspace type with its key modules by name, "
    "and asks if they'd like to proceed. "
    "Be conversational and natural, not robotic or list-heavy."
)


def _message_text(payload: object) -> str:
    if isinstance(payload, AIMessage):
        return str(payload.content)
    if isinstance(payload, str):
        return payload
    return ""


async def bundle_confirmer(  # pylint: disable=too-many-locals
    state: OnboardingState, config: RunnableConfig
) -> Command:
    session_id = state.get("session_id", "")
    session_logger = get_session_logger(__name__, session_id)
    if state.get("confirmed", False):
        return Command(goto="json_assembler")

    intents = state.get("onboarding_intents")
    fallback_bundle = CATALOG.get_fallback()
    bundle_key = (
        intents.bundle if intents and intents.bundle else fallback_bundle.bundle_key
    )
    bundle = CATALOG.get(bundle_key) or CATALOG.get_fallback()
    slots = dict(state.get("slots", {}))
    confirmation_message = ""
    try:
        settings = get_settings()
        model = get_openai_chat_model(temperature=settings.CONVERSATIONAL_TEMPERATURE)
        response = await model.ainvoke(
            [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(
                    content=(
                        f"Recommended workspace: {bundle.display_name} "
                        f"({bundle.bundle_key})\n"
                        f"Modules included: {', '.join(bundle.default_modules)}\n"
                        f"What we know about the user: {slots}"
                    ),
                ),
            ],
        )
        confirmation_message = _message_text(response).strip()
    except (RuntimeError, TypeError, ValueError) as exc:
        session_logger.error("Bundle confirmation generation failed: %s", exc)

    if not confirmation_message:
        confirmation_message = (
            f"I recommend {bundle.display_name} with modules "
            f"{', '.join(bundle.default_modules)}. Does this look right?"
        )

    token = var_child_runnable_config.set(config)
    try:
        user_reply = interrupt(
            {
                "type": "bundle_suggestion",
                "bundle": bundle.bundle_key,
                "modules": bundle.default_modules,
                "message": confirmation_message,
            },
        )
    finally:
        var_child_runnable_config.reset(token)

    session_logger.info("Bundle confirmed for bundle=%s", bundle.bundle_key)
    step = f"Bundle confirmed ✓ **{bundle.display_name}** — generating workspace..."
    return Command(
        goto="json_assembler",
        update={
            "confirmed": True,
            "messages": [HumanMessage(content=str(user_reply or ""), name="user")],
            "thinking_trace": [step],
        },
    )
