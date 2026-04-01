from __future__ import annotations

from typing import Annotated

from langgraph.graph.message import MessagesState

from .intent_schemas import OnboardingIntents


def _append_trace(left: list[str] | None, right: list[str]) -> list[str]:
    """Null-safe reducer: appends new trace steps to existing list."""
    return (left or []) + (right or [])


class OnboardingState(MessagesState):
    session_id: str
    slots: dict[str, object]
    onboarding_intents: OnboardingIntents | None
    turn_count: int
    confirmed: bool
    generation_json: dict[str, object] | None
    dummy_data_json: dict[str, object] | None
    clarification_queue: list[str]
    bundle_candidates: list[str]
    auth_token: str | None
    user_id: str | None
    thinking_trace: Annotated[list[str], _append_trace]
