"""Unit tests for enhanced sample data population and emit config enrichment."""

from __future__ import annotations

from pathlib import Path

import pytest

from agents.preview_generator.nodes.sample_data import _dept_pool, generate_sample_data
from agents.preview_generator.nodes.emit import emit_preview
from agents.preview_generator.state import PreviewGeneratorState
from agents.preview_generator.schemas import (
    UserContext,
    TeamDetail,
    KpiMetric,
)
from catalog.bundle_catalog import BundleCatalog
from domain.models.extraction_result import (
    ExtractionResult,
    PersonalizationSignals,
    ClassificationSignals,
)

REGISTRY_PATH = (
    Path(__file__).resolve().parents[3] / "src/templates/bundle_registry.yaml"
)


@pytest.fixture
def catalog() -> BundleCatalog:
    return BundleCatalog(REGISTRY_PATH)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_kpi(key: str) -> KpiMetric:
    return KpiMetric(
        key=key,
        label=key.replace("_", " ").title(),
        type="percentage",
        source_service="kpi-service",
        sample_value=75.0,
    )


def _make_full_state(
    catalog: BundleCatalog,
    bundle_key: str = "ticketing",
    registry_key: str = "ticketing",
    user_context: UserContext | None = None,
    extraction_result: ExtractionResult | None = None,
) -> PreviewGeneratorState:
    """Build a fully-populated PreviewGeneratorState ready for emit_preview."""
    # Run generate_sample_data first to get realistic sample data
    state = PreviewGeneratorState(
        session_id="test-session",
        bundle_key=bundle_key,
        conversation_history=[],
        data_tier="tier_1",
        user_context=user_context,
        extraction_result=extraction_result,
        resolved_bundle_ids=[registry_key],
        feature_flags={
            "tickets-module": True,
            "dashboard-module": True,
            "kpi-module": True,
        },
        permission_services=["tickets", "kpi"],
        landing_pages=[{"id": 101, "module": "Tickets", "path": "/tickets"}],
        kpi_metrics=[_make_kpi("avg_resolution_time"), _make_kpi("sla_compliance")],
        schema_valid=True,
        catalog=catalog,
    )
    # Populate sample data via the node
    sample_updates = generate_sample_data(state)
    return state.model_copy(update=sample_updates)


# ---------------------------------------------------------------------------
# _dept_pool tests
# ---------------------------------------------------------------------------


def test_dept_pool_uses_user_context_teams():
    """UserContext.teams takes highest priority over all other sources."""
    ctx = UserContext(
        teams=[TeamDetail(name="Legal"), TeamDetail(name="Finance")]
    )
    result = _dept_pool("project_mgmt", ctx, branch_names=["NYC", "London"])
    assert result == ["Legal", "Finance"]


def test_dept_pool_uses_branch_names_fallback():
    """branch_names is used when no teams are set in UserContext."""
    ctx = UserContext()  # no teams
    result = _dept_pool("project_mgmt", ctx, branch_names=["NYC", "London"])
    assert result == ["NYC", "London"]


def test_dept_pool_uses_bundle_default_when_nothing():
    """Falls back to _DEPARTMENTS_BY_BUNDLE when no teams and no branch_names."""
    result = _dept_pool("project_mgmt", None, branch_names=None)
    assert "Operations" in result or "Product" in result or "Engineering" in result


def test_dept_pool_bundle_default_for_unknown_bundle():
    """Unknown bundle key returns generic default."""
    result = _dept_pool("unknown_bundle", None, branch_names=None)
    assert result == ["Operations", "Product", "Engineering"]


# ---------------------------------------------------------------------------
# Branch names flow through generate_sample_data
# ---------------------------------------------------------------------------


def test_branch_names_flow_through_employees(catalog: BundleCatalog):
    """ExtractionResult.personalization_signals.branch_names drives dept assignment."""
    extraction = ExtractionResult(
        session_id="test-session",
        personalization_signals=PersonalizationSignals(
            branch_names=["HQ", "Remote"]
        ),
        classification_signals=ClassificationSignals(),
    )
    state = PreviewGeneratorState(
        session_id="test-session",
        bundle_key="project_mgmt",
        conversation_history=[],
        data_tier="tier_1",
        extraction_result=extraction,
        catalog=catalog,
    )
    updates = generate_sample_data(state)
    employees = updates["sample_employees"]
    assert len(employees) > 0
    for emp in employees:
        assert emp["department"] in ("HQ", "Remote"), (
            f"Employee department {emp['department']!r} not in branch_names"
        )


def test_user_context_teams_override_branch_names(catalog: BundleCatalog):
    """UserContext.teams beats branch_names from ExtractionResult."""
    extraction = ExtractionResult(
        session_id="test-session",
        personalization_signals=PersonalizationSignals(
            branch_names=["HQ", "Remote"]
        ),
        classification_signals=ClassificationSignals(),
    )
    ctx = UserContext(teams=[TeamDetail(name="AlphaTeam"), TeamDetail(name="BetaTeam")])
    state = PreviewGeneratorState(
        session_id="test-session",
        bundle_key="project_mgmt",
        conversation_history=[],
        data_tier="tier_1",
        user_context=ctx,
        extraction_result=extraction,
        catalog=catalog,
    )
    updates = generate_sample_data(state)
    employees = updates["sample_employees"]
    for emp in employees:
        assert emp["department"] in ("AlphaTeam", "BetaTeam")


# ---------------------------------------------------------------------------
# emit config fields populated from sample data
# ---------------------------------------------------------------------------


def test_config_ticket_statuses_populated(catalog: BundleCatalog):
    """ticketing bundle config should have non-empty work_order_statuses."""
    state = _make_full_state(catalog, bundle_key="ticketing", registry_key="ticketing")
    result = emit_preview(state)
    output = result["output"]
    config = output["generation_json"]["config"]
    assert "work_order_statuses" in config
    assert isinstance(config["work_order_statuses"], list)
    assert len(config["work_order_statuses"]) > 0


def test_config_task_statuses_populated(catalog: BundleCatalog):
    """project_mgmt bundle config should have non-empty task_statuses."""
    state = _make_full_state(catalog, bundle_key="project_mgmt", registry_key="project_mgmt")
    result = emit_preview(state)
    output = result["output"]
    config = output["generation_json"]["config"]
    assert "task_statuses" in config
    assert isinstance(config["task_statuses"], list)
    assert len(config["task_statuses"]) > 0


def test_config_hr_hub_statuses_populated(catalog: BundleCatalog):
    """hr_hub bundle config should have non-empty default_statuses."""
    state = _make_full_state(catalog, bundle_key="hr_management", registry_key="hr_hub")
    result = emit_preview(state)
    output = result["output"]
    config = output["generation_json"]["config"]
    assert "default_statuses" in config
    assert isinstance(config["default_statuses"], list)
    assert len(config["default_statuses"]) > 0


def test_config_milestone_statuses_static_defaults(catalog: BundleCatalog):
    """project_mgmt milestone_statuses should be sensible static values."""
    state = _make_full_state(catalog, bundle_key="project_mgmt", registry_key="project_mgmt")
    result = emit_preview(state)
    output = result["output"]
    config = output["generation_json"]["config"]
    assert "milestone_statuses" in config
    expected = {"Planning", "In Progress", "Completed", "On Hold"}
    assert set(config["milestone_statuses"]) == expected


def test_config_kpi_definitions_unchanged(catalog: BundleCatalog):
    """kpi_definitions still contains the KPI keys regardless of bundle."""
    state = _make_full_state(catalog, bundle_key="ticketing", registry_key="ticketing")
    result = emit_preview(state)
    output = result["output"]
    config = output["generation_json"]["config"]
    assert "kpi_definitions" in config
    kpi_keys = [k.key for k in state.kpi_metrics]
    assert config["kpi_definitions"] == kpi_keys


def test_config_queue_names_populated_for_hr(catalog: BundleCatalog):
    """hr_hub queue_names derived from employee departments."""
    state = _make_full_state(catalog, bundle_key="hr_management", registry_key="hr_hub")
    result = emit_preview(state)
    output = result["output"]
    config = output["generation_json"]["config"]
    assert "queue_names" in config
    assert isinstance(config["queue_names"], list)
    assert len(config["queue_names"]) > 0
