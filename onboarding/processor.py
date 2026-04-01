from __future__ import annotations

from collections.abc import Sequence
from uuid import uuid4

from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.types import Command

from catalog import BundleCatalog
from core import Database, get_session_logger

from .graph import build_onboarding_graph

_CATALOG = BundleCatalog()


def _thread_config(session_id: str) -> dict[str, dict[str, str]]:
    return {"configurable": {"thread_id": session_id}}


def _extract_interrupt(snapshot: object) -> dict[str, object] | None:
    if not getattr(snapshot, "next", None):
        return None

    tasks = getattr(snapshot, "tasks", [])
    if not tasks:
        return None
    interrupts = getattr(tasks[0], "interrupts", [])
    if not interrupts:
        return None
    value = interrupts[0].value
    if isinstance(value, dict):
        return {str(key): value[key] for key in value}
    return {"message": str(value)}


def _last_message(messages: Sequence[BaseMessage]) -> str:
    if not messages:
        return ""
    content = messages[-1].content
    return str(content) if isinstance(content, str) else str(content)


def _build_interpretation(snapshot: object) -> dict[str, object]:
    values = snapshot.values if hasattr(snapshot, "values") else {}
    intents = values.get("onboarding_intents")
    slots = dict(values.get("slots", {}))
    bundle_key = intents.bundle if intents else None
    bundle = _CATALOG.get(bundle_key) if bundle_key else None

    missing_slots: list[str] = []
    if bundle_key:
        required = _CATALOG.get_required_slots(bundle_key)
        missing_slots = [s for s in required if not slots.get(s)]

    return {
        "bundle": bundle_key,
        "bundle_display_name": bundle.display_name if bundle else None,
        "entity_type": intents.entity_type if intents else None,
        "raw_intent": intents.raw_intent if intents else None,
        "industry_hint": intents.industry_hint if intents else None,
        "confidence": intents.confidence if intents else None,
        "confirmed": bool(values.get("confirmed", False)),
        "slots": slots,
        "missing_slots": missing_slots,
        "turn_count": int(values.get("turn_count", 0)),
        "thinking_trace": list(values.get("thinking_trace", [])),
    }


class OnboardingProcessor:
    async def start_session(
        self,
        message: str,
        user_id: str | None = None,
        auth_token: str | None = None,
    ) -> dict[str, object]:
        session_id = str(uuid4())
        await Database.initialize()
        config = _thread_config(session_id)
        session_logger = get_session_logger(__name__, session_id)
        initial_state = {
            "session_id": session_id,
            "messages": [HumanMessage(content=message, name="user")],
            "slots": {},
            "onboarding_intents": None,
            "turn_count": 0,
            "confirmed": False,
            "generation_json": None,
            "dummy_data_json": None,
            "clarification_queue": [],
            "bundle_candidates": [],
            "auth_token": auth_token,
            "user_id": user_id,
            "thinking_trace": [],
        }
        async with Database.get_checkpointer() as checkpointer:
            graph = build_onboarding_graph(checkpointer=checkpointer)
            session_logger.info("Starting onboarding session")
            await graph.ainvoke(initial_state, config=config)
            return await self._build_response(graph, config, session_id)

    async def reply(self, session_id: str, message: str) -> dict[str, object]:
        await Database.initialize()
        config = _thread_config(session_id)
        session_logger = get_session_logger(__name__, session_id)
        async with Database.get_checkpointer() as checkpointer:
            graph = build_onboarding_graph(checkpointer=checkpointer)
            snapshot = await graph.aget_state(config)
            if snapshot.next:
                session_logger.info("Resuming interrupted onboarding session")
                await graph.ainvoke(Command(resume=message), config=config)
            else:
                session_logger.info("Continuing onboarding session")
                await graph.ainvoke(
                    {"messages": [HumanMessage(content=message, name="user")]},
                    config=config,
                )
            return await self._build_response(graph, config, session_id)

    async def _build_response(
        self,
        graph: object,
        config: dict[str, dict[str, str]],
        session_id: str,
    ) -> dict[str, object]:
        snapshot = await graph.aget_state(config)  # type: ignore[attr-defined]
        interpretation = _build_interpretation(snapshot)
        interrupt_data = _extract_interrupt(snapshot)
        if interrupt_data is not None:
            return {
                "status": "awaiting_input",
                "session_id": session_id,
                "interrupt": interrupt_data,
                "interpretation": interpretation,
            }

        values = snapshot.values if hasattr(snapshot, "values") else {}
        generation_json = values.get("generation_json")
        dummy_data_json = values.get("dummy_data_json")
        if isinstance(generation_json, dict) and isinstance(dummy_data_json, dict):
            return {
                "status": "complete",
                "session_id": session_id,
                "generation_json": generation_json,
                "dummy_data_json": dummy_data_json,
                "interpretation": interpretation,
            }

        messages = values.get("messages", [])
        return {
            "status": "in_progress",
            "session_id": session_id,
            "message": _last_message(messages),
            "interpretation": interpretation,
        }
