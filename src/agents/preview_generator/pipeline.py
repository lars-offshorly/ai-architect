from __future__ import annotations

from langgraph.graph import END, StateGraph

from .nodes.data_tier import select_data_tier
from .nodes.emit import emit_preview
from .nodes.extract_context import extract_user_context
from .nodes.kpi import build_kpi_metrics
from .nodes.resolve_flags import resolve_bundles_to_flags
from .nodes.sample_data import generate_sample_data
from .nodes.validate import ROUTE_EMIT, ROUTE_RETRY, route_after_validation, validate_schema
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

_workflow = StateGraph(PreviewGeneratorState)

_workflow.add_node("extract_user_context",     extract_user_context)
_workflow.add_node("resolve_bundles_to_flags", resolve_bundles_to_flags)
_workflow.add_node("select_data_tier",         select_data_tier)
_workflow.add_node("generate_sample_data",     generate_sample_data)
_workflow.add_node("build_kpi_metrics",        build_kpi_metrics)
_workflow.add_node("validate_schema",          validate_schema)
_workflow.add_node("emit_preview",             emit_preview)

_workflow.set_entry_point("extract_user_context")

_workflow.add_edge("extract_user_context",     "resolve_bundles_to_flags")
_workflow.add_edge("resolve_bundles_to_flags", "select_data_tier")
_workflow.add_edge("select_data_tier",         "generate_sample_data")
_workflow.add_edge("generate_sample_data",     "build_kpi_metrics")
_workflow.add_edge("build_kpi_metrics",        "validate_schema")

_workflow.add_conditional_edges(
    "validate_schema",
    route_after_validation,
    {
        ROUTE_EMIT:  "emit_preview",
        ROUTE_RETRY: "resolve_bundles_to_flags",
    },
)

_workflow.add_edge("emit_preview", END)

# Compiled graph — imported and invoked by PreviewGeneratorService
compiled_graph = _workflow.compile()
