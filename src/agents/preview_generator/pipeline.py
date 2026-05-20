"""Compiled LangGraph pipeline for the preview generator agent."""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from .nodes.data_tier import select_data_tier
from .nodes.emit import emit_preview
from .nodes.extract_context import extract_user_context
from .nodes.kpi import build_kpi_metrics
from .nodes.resolve_flags import resolve_bundles_to_flags
from .nodes.sample_data import generate_sample_data
from .nodes.validate import (
    ROUTE_EMIT,
    ROUTE_RETRY,
    route_after_validation,
    validate_schema,
)
from .state import PreviewGeneratorState

# ---------------------------------------------------------------------------
# Graph definition
#
# Linear flow:
#   extract_user_context
#     → resolve_bundles_to_flags
#       → select_data_tier
#         → generate_sample_data
#           → build_kpi_metrics
#             → validate_schema
#               ┌─ [valid or retries exhausted] → emit_preview → END
#               └─ [invalid, retries remain]    → resolve_bundles_to_flags (retry)
# ---------------------------------------------------------------------------

def _build_workflow(*, skip_sample_data: bool) -> StateGraph:
    workflow = StateGraph(PreviewGeneratorState)

    workflow.add_node("extract_user_context", extract_user_context)
    workflow.add_node("resolve_bundles_to_flags", resolve_bundles_to_flags)
    workflow.add_node("select_data_tier", select_data_tier)
    workflow.add_node("generate_sample_data", generate_sample_data)
    workflow.add_node("build_kpi_metrics", build_kpi_metrics)
    workflow.add_node("validate_schema", validate_schema)
    workflow.add_node("emit_preview", emit_preview)

    workflow.set_entry_point("extract_user_context")

    workflow.add_edge("extract_user_context", "resolve_bundles_to_flags")
    workflow.add_edge("resolve_bundles_to_flags", "select_data_tier")
    if skip_sample_data:
        workflow.add_edge("select_data_tier", "build_kpi_metrics")
    else:
        workflow.add_edge("select_data_tier", "generate_sample_data")
        workflow.add_edge("generate_sample_data", "build_kpi_metrics")
    workflow.add_edge("build_kpi_metrics", "validate_schema")

    workflow.add_conditional_edges(
        "validate_schema",
        route_after_validation,
        {
            ROUTE_EMIT: "emit_preview",
            ROUTE_RETRY: "resolve_bundles_to_flags",
        },
    )

    workflow.add_edge("emit_preview", END)
    return workflow


# Compiled graphs — selected by PreviewGeneratorService.emit_v2 flag.
compiled_graph = _build_workflow(skip_sample_data=False).compile()
compiled_graph_skip_sample_data = _build_workflow(skip_sample_data=True).compile()
