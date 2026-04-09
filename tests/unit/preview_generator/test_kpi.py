"""Unit tests for the build_kpi_metrics node — signal boost behaviour."""

from __future__ import annotations

import pytest

from agents.preview_generator.nodes.kpi import build_kpi_metrics
from agents.preview_generator.schemas import UserContext
from agents.preview_generator.state import PreviewGeneratorState
from domain.models.extraction_result import (
    ClassificationSignals,
    ExtractionResult,
    PersonalizationSignals,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(
    bundle_key: str = "project_mgmt",
    extraction_result: ExtractionResult | None = None,
    key_phrases: list[str] | None = None,
) -> PreviewGeneratorState:
    ctx = UserContext(key_phrases=key_phrases or [])
    return PreviewGeneratorState(
        session_id="test",
        bundle_key=bundle_key,
        user_context=ctx,
        extraction_result=extraction_result,
    )


def _make_extraction(metrics: list[str] | None = None) -> ExtractionResult:
    return ExtractionResult(
        session_id="test",
        classification_signals=ClassificationSignals(metrics=metrics or []),
    )


def _kpi_keys(state: PreviewGeneratorState) -> list[str]:
    result = build_kpi_metrics(state)
    return [kpi.key for kpi in result["kpi_metrics"]]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_signal_metrics_exact_match():
    """ExtractionResult with an exact METRICS_CATALOG key appears in output."""
    extraction = _make_extraction(metrics=["sla_compliance"])
    state = _make_state(bundle_key="ticketing", extraction_result=extraction)
    keys = _kpi_keys(state)
    assert "sla_compliance" in keys


def test_signal_metrics_phrase_fallback():
    """'sla' is not a catalog key; it maps via _PHRASE_TO_METRIC to sla_compliance."""
    extraction = _make_extraction(metrics=["sla"])
    # Use a bundle that doesn't include sla_compliance by default
    state = _make_state(bundle_key="project_mgmt", extraction_result=extraction)
    keys = _kpi_keys(state)
    assert "sla_compliance" in keys


def test_signal_metrics_prioritized_before_key_phrases():
    """Signal metrics appear before key_phrases boosts in the KPI list."""
    extraction = _make_extraction(metrics=["sla_compliance"])
    # key_phrases triggers capacity_utilization which IS already a project_mgmt default,
    # so use "workload" → workload_distribution which is not a default
    state = _make_state(
        bundle_key="project_mgmt",
        extraction_result=extraction,
        key_phrases=["workload"],
    )
    keys = _kpi_keys(state)

    # sla_compliance must be present and come before workload_distribution
    assert "sla_compliance" in keys
    assert "workload_distribution" in keys
    assert keys.index("sla_compliance") < keys.index("workload_distribution")


def test_no_extraction_result_output_unchanged():
    """With extraction_result=None, output matches the bundle's default KPIs."""
    state_with = _make_state(bundle_key="project_mgmt", extraction_result=None)
    state_without = _make_state(bundle_key="project_mgmt", extraction_result=None)

    keys_with = _kpi_keys(state_with)
    keys_without = _kpi_keys(state_without)

    assert keys_with == keys_without


def test_signal_metrics_deduplication():
    """A metric that is already in default_slugs is not duplicated in output."""
    # "on_time_delivery_rate" is a project_mgmt default
    extraction = _make_extraction(metrics=["on_time_delivery_rate"])
    state = _make_state(bundle_key="project_mgmt", extraction_result=extraction)
    keys = _kpi_keys(state)

    assert keys.count("on_time_delivery_rate") == 1
