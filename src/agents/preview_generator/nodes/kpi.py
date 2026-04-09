"""Pipeline node: builds KPI metric definitions for the selected bundle."""

from __future__ import annotations

from core.logging import get_logger

from ..bundles.registry import BUNDLE_REGISTRY, METRICS_CATALOG
from ..schemas import KpiMetric
from ..state import PreviewGeneratorState

logger = get_logger(__name__)

_FALLBACK_SLUGS: list[str] = ["capacity_utilization", "active_work_items"]

# ---------------------------------------------------------------------------
# Sample values per metric type — deterministic, index-based
# ---------------------------------------------------------------------------

_SAMPLE_VALUES: dict[str, list[float | int | str]] = {
    "percentage": [87.5, 92.1, 78.4, 95.0, 83.2],
    "count": [142, 38, 217, 15, 67],
    "duration": [3.2, 1.8, 5.4, 2.1, 4.7],  # days
    "status": ["Healthy", "At Risk", "Healthy", "On Track", "Healthy"],
    "ratio": [0.72, 0.85, 0.61, 0.90, 0.78],
}

# Key phrase → extra metric slugs to append (Phase 1: keyword-driven boost)
_PHRASE_TO_METRIC: dict[str, str] = {
    "on time": "on_time_delivery_rate",
    "deadline": "upcoming_deadlines",
    "delivery": "on_time_delivery_rate",
    "resolution": "avg_resolution_time",
    "sla": "sla_compliance",
    "capacity": "capacity_utilization",
    "utilization": "capacity_utilization",
    "workload": "workload_distribution",
    "headcount": "active_headcount",
    "attendance": "attendance_rate",
    "billable": "billable_vs_nonbillable",
    "cycle time": "cycle_time",
    "case load": "case_load_distribution",
}


def _pick_value(metric_type: str, index: int) -> float | int | str:
    pool = _SAMPLE_VALUES.get(metric_type, _SAMPLE_VALUES["count"])
    return pool[index % len(pool)]


def build_kpi_metrics(  # pylint: disable=too-many-branches
    state: PreviewGeneratorState,
) -> dict:
    """Assemble KPI metrics for the resolved bundle.

    Starts from bundle's default_metrics list, then boosts with any
    extra metrics implied by UserContext key_phrases. Deduplicates.
    Each metric entry includes a sample value for preview display.

    Returns: {"kpi_metrics": list[dict]}
    """
    bundle_key = state.bundle_key
    bundle = BUNDLE_REGISTRY.get(bundle_key, {})
    default_slugs: list[str] = list(bundle.get("default_metrics", []))

    # Boost from classification_signals.metrics in ExtractionResult (priority boost)
    signal_boost_slugs: list[str] = []
    if state.extraction_result is not None:
        for metric in state.extraction_result.classification_signals.metrics:
            slug: str | None
            if metric in METRICS_CATALOG:
                slug = metric
            else:
                slug = _PHRASE_TO_METRIC.get(metric)
            if slug and slug not in default_slugs:
                signal_boost_slugs.append(slug)

    # Boost from key phrases in UserContext
    boost_slugs: list[str] = []
    if state.user_context and state.user_context.key_phrases:
        for phrase in state.user_context.key_phrases:
            phrase_slug = _PHRASE_TO_METRIC.get(phrase)
            if phrase_slug and phrase_slug not in default_slugs:
                boost_slugs.append(phrase_slug)

    # Deduplicate while preserving order
    all_slugs: list[str] = []
    seen: set[str] = set()
    for slug in default_slugs + signal_boost_slugs + boost_slugs:
        if slug not in seen and slug in METRICS_CATALOG:
            seen.add(slug)
            all_slugs.append(slug)

    # Fallback: at least show capacity_utilization and active_work_items
    if not all_slugs:
        all_slugs = _FALLBACK_SLUGS

    # Build output records
    kpi_metrics: list[KpiMetric] = []
    for i, slug in enumerate(all_slugs):
        catalog_entry = METRICS_CATALOG.get(slug)
        if catalog_entry is None:
            continue
        kpi_metrics.append(
            KpiMetric(
                key=catalog_entry["key"],
                label=catalog_entry["label"],
                type=catalog_entry["type"],
                source_service=catalog_entry["source_service"],
                sample_value=_pick_value(catalog_entry["type"], i),
            )
        )

    logger.info(
        "session=%s — built %d KPI metrics for bundle=%r "
        "(default=%d signal_boost=%d boost=%d)",
        state.session_id,
        len(kpi_metrics),
        bundle_key,
        len(default_slugs),
        len(signal_boost_slugs),
        len(boost_slugs),
    )
    return {"kpi_metrics": kpi_metrics}
