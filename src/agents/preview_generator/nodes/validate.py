from __future__ import annotations

from core.logging import get_logger

from ..state import PreviewGeneratorState

logger = get_logger(__name__)

# Routing tokens — must match keys in pipeline.py's conditional_edges map
ROUTE_EMIT   = "emit_preview"
ROUTE_RETRY  = "resolve_bundles_to_flags"


def validate_schema(state: PreviewGeneratorState) -> dict:
    """Validate that all pipeline stages produced usable data.

    Rules (Phase 1):
      1. feature_flags must be non-empty (flags were resolved)
      2. sample_employees must have at least one record
      3. kpi_metrics must be a non-empty list

    On failure:
      - If retry_count < max_retries → increment retry_count, mark invalid
        (pipeline.py will route back to resolve_bundles_to_flags)
      - If retries exhausted → mark invalid but proceed to emit_preview
        with best-effort data (emit handles the degraded case)

    Returns updates for: schema_valid, validation_errors, retry_count
    """
    errors: list[str] = []

    if not state.feature_flags:
        errors.append("feature_flags is empty — bundle resolution produced no flags")

    if not state.sample_employees:
        errors.append("sample_employees is empty — sample data generation failed")

    if not state.kpi_metrics:
        errors.append("kpi_metrics is empty — KPI assembly produced no metrics")

    if errors:
        new_retry_count = state.retry_count + 1
        logger.warning(
            "session=%s — validation failed (attempt %d/%d): %s",
            state.session_id,
            new_retry_count,
            state.max_retries,
            "; ".join(errors),
        )
        return {
            "schema_valid": False,
            "validation_errors": errors,
            "retry_count": new_retry_count,
        }

    logger.info(
        "session=%s — validation passed: flags=%d employees=%d kpis=%d",
        state.session_id,
        sum(1 for v in state.feature_flags.values() if v),
        len(state.sample_employees),
        len(state.kpi_metrics),
    )
    return {
        "schema_valid": True,
        "validation_errors": [],
        "retry_count": state.retry_count,
    }


def route_after_validation(state: PreviewGeneratorState) -> str:
    """Routing function for the conditional edge out of validate_schema.

    Called by pipeline.py's add_conditional_edges.
    Returns a routing token that maps to a node name.
    """
    if state.schema_valid:
        return ROUTE_EMIT

    if state.retry_count < state.max_retries:
        logger.info(
            "session=%s — routing back to resolve_bundles_to_flags (retry %d/%d)",
            state.session_id,
            state.retry_count,
            state.max_retries,
        )
        return ROUTE_RETRY

    # Retries exhausted — proceed to emit with whatever data we have
    logger.warning(
        "session=%s — max retries reached, proceeding to emit with partial data",
        state.session_id,
    )
    return ROUTE_EMIT
