"""Pipeline node: builds KPI metric definitions for the selected bundle."""

from __future__ import annotations

from core.logging import get_logger

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


def _resolve_default_slugs(state: PreviewGeneratorState, bundle_key: str) -> list[str]:
    catalog = state.catalog
    if catalog is None:
        return []
    bundle = catalog.get(bundle_key)
    if bundle is None:
        logger.warning(
            "session=%s — bundle_key=%r not in catalog, using fallbacks",
            state.session_id,
            bundle_key,
        )
        return []
    return bundle.metadata.kpis if bundle.metadata else []


def _collect_signal_boost_slugs(
    state: PreviewGeneratorState,
    metrics_catalog: dict[str, dict[str, object]],
    default_slugs: list[str],
) -> list[str]:
    if state.extraction_result is None:
        return []
    signal_boost_slugs: list[str] = []
    for metric in state.extraction_result.classification_signals.metrics:
        slug = metric if metric in metrics_catalog else _PHRASE_TO_METRIC.get(metric)
        if slug and slug not in default_slugs:
            signal_boost_slugs.append(slug)
    return signal_boost_slugs


def _collect_context_boost_slugs(
    state: PreviewGeneratorState,
    default_slugs: list[str],
) -> list[str]:
    if not state.user_context or not state.user_context.key_phrases:
        return []
    boost_slugs: list[str] = []
    for phrase in state.user_context.key_phrases:
        phrase_slug = _PHRASE_TO_METRIC.get(phrase)
        if phrase_slug and phrase_slug not in default_slugs:
            boost_slugs.append(phrase_slug)
    return boost_slugs


def _dedupe_valid_slugs(
    metrics_catalog: dict[str, dict[str, object]],
    *slug_lists: list[str],
) -> list[str]:
    all_slugs: list[str] = []
    seen: set[str] = set()
    for slug in [s for slugs in slug_lists for s in slugs]:
        if slug not in seen and slug in metrics_catalog:
            seen.add(slug)
            all_slugs.append(slug)
    return all_slugs


def build_kpi_metrics(state: PreviewGeneratorState) -> dict:
    """Assemble KPI metrics for the resolved bundle.

    Starts from bundle's default_metrics list, then boosts with any
    extra metrics implied by UserContext key_phrases. Deduplicates.
    Each metric entry includes a sample value for preview display.

    Returns: {"kpi_metrics": list[dict]}
    """
    if state.catalog is None:
        logger.error("session=%s — BundleCatalog missing in state", state.session_id)
        return {"kpi_metrics": []}

    metrics_catalog = state.catalog.get_metrics_catalog()
    bundle_key = state.bundle_key
    default_slugs = _resolve_default_slugs(state, bundle_key)
    signal_boost_slugs = _collect_signal_boost_slugs(
        state, metrics_catalog, default_slugs
    )
    boost_slugs = _collect_context_boost_slugs(state, default_slugs)
    all_slugs = _dedupe_valid_slugs(
        metrics_catalog, default_slugs, signal_boost_slugs, boost_slugs
    )

    # Fallback: at least show capacity_utilization and active_work_items
    if not all_slugs:
        all_slugs = [s for s in _FALLBACK_SLUGS if s in metrics_catalog]

    # Build output records
    kpi_metrics: list[KpiMetric] = []
    for i, slug in enumerate(all_slugs):
        catalog_entry = metrics_catalog.get(slug)
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
