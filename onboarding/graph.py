from __future__ import annotations

from typing import TYPE_CHECKING

from langchain_core.runnables import Runnable
from langgraph.graph import START, StateGraph

from .nodes import (
    bundle_confirmer,
    clarification,
    conversation_classifier,
    intent_extraction,
    json_assembler,
    slot_filler,
)
from .states import OnboardingState

if TYPE_CHECKING:
    from langgraph.checkpoint.base import BaseCheckpointSaver


def build_onboarding_graph(
    checkpointer: BaseCheckpointSaver | None = None,
) -> Runnable:
    builder = StateGraph(OnboardingState)
    builder.add_node("conversation_classifier", conversation_classifier)
    builder.add_node("intent_extraction", intent_extraction)
    builder.add_node("slot_filler", slot_filler)
    builder.add_node("clarification", clarification)
    builder.add_node("bundle_confirmer", bundle_confirmer)
    builder.add_node("json_assembler", json_assembler)
    builder.add_edge(START, "conversation_classifier")
    return builder.compile(checkpointer=checkpointer)
