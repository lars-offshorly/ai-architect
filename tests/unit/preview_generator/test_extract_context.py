"""Unit tests for extract_user_context node — three-tier logic."""

from __future__ import annotations

import pytest

from agents.preview_generator.nodes.extract_context import extract_user_context
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
    extraction_result: ExtractionResult | None = None,
    preselected_intent: str | None = None,
    history: list[dict] | None = None,
) -> PreviewGeneratorState:
    return PreviewGeneratorState(
        session_id="test-session",
        bundle_key="project_mgmt",
        conversation_history=history or [],
        extraction_result=extraction_result,
        preselected_intent=preselected_intent,
    )


def _make_extraction(
    company_name: str | None = None,
    employee_names: list[str] | None = None,
    role_names: list[str] | None = None,
    department_names: list[str] | None = None,
    domain_hints: list[str] | None = None,
    workflow_hints: list[str] | None = None,
    metrics: list[str] | None = None,
    terminology: dict[str, str] | None = None,
) -> ExtractionResult:
    return ExtractionResult(
        session_id="test-session",
        personalization_signals=PersonalizationSignals(
            company_name=company_name,
            employee_names=employee_names or [],
            role_names=role_names or [],
            department_names=department_names or [],
            terminology=terminology or {},
        ),
        classification_signals=ClassificationSignals(
            domain_hints=domain_hints or [],
            workflow_hints=workflow_hints or [],
            metrics=metrics or [],
        ),
    )


# ---------------------------------------------------------------------------
# Tier 1 — ExtractionResult present
# ---------------------------------------------------------------------------


def test_tier1_maps_company_name() -> None:
    er = _make_extraction(company_name="TechCorp")
    result = extract_user_context(_make_state(extraction_result=er))
    assert result["user_context"].company_name == "TechCorp"


def test_tier1_maps_department_names_to_teams() -> None:
    er = _make_extraction(department_names=["Engineering", "Legal"])
    ctx = extract_user_context(_make_state(extraction_result=er))["user_context"]
    team_names = [t.name for t in ctx.teams]
    assert "Engineering" in team_names
    assert "Legal" in team_names


def test_tier1_maps_employee_names_to_people() -> None:
    er = _make_extraction(employee_names=["Alice Tan", "Bob Reyes"])
    ctx = extract_user_context(_make_state(extraction_result=er))["user_context"]
    person_names = [p.name for p in ctx.people]
    assert "Alice Tan" in person_names
    assert "Bob Reyes" in person_names


def test_tier1_maps_role_names_to_people() -> None:
    er = _make_extraction(role_names=["HR Manager", "Team Lead"])
    ctx = extract_user_context(_make_state(extraction_result=er))["user_context"]
    person_roles = [p.role for p in ctx.people]
    assert "HR Manager" in person_roles
    assert "Team Lead" in person_roles


def test_tier1_maps_domain_hint_to_industry() -> None:
    er = _make_extraction(domain_hints=["Legal / Law Firm", "Litigation"])
    ctx = extract_user_context(_make_state(extraction_result=er))["user_context"]
    assert ctx.industry_detail == "Legal / Law Firm"


def test_tier1_maps_workflow_hints_to_methodology_agile() -> None:
    er = _make_extraction(workflow_hints=["agile sprints", "kanban board"])
    ctx = extract_user_context(_make_state(extraction_result=er))["user_context"]
    assert ctx.work_methodology == "agile"


def test_tier1_maps_workflow_hints_to_methodology_waterfall() -> None:
    er = _make_extraction(workflow_hints=["waterfall milestones"])
    ctx = extract_user_context(_make_state(extraction_result=er))["user_context"]
    assert ctx.work_methodology == "waterfall"


def test_tier1_maps_metrics_to_key_phrases() -> None:
    er = _make_extraction(metrics=["sla_compliance", "avg_resolution_time"])
    ctx = extract_user_context(_make_state(extraction_result=er))["user_context"]
    assert "sla_compliance" in ctx.key_phrases
    assert "avg_resolution_time" in ctx.key_phrases


def test_tier1_maps_terminology_values_to_key_phrases() -> None:
    er = _make_extraction(terminology={"ticket": "matter", "project": "engagement"})
    ctx = extract_user_context(_make_state(extraction_result=er))["user_context"]
    assert "matter" in ctx.key_phrases
    assert "engagement" in ctx.key_phrases


def test_tier1_keyword_fills_company_size_gap() -> None:
    """ExtractionResult provides company_name; keyword scan adds company_size."""
    er = _make_extraction(company_name="Apex Corp")
    history = [{"role": "user", "content": "We are an enterprise company with 5000 employees."}]
    ctx = extract_user_context(_make_state(extraction_result=er, history=history))["user_context"]
    assert ctx.company_name == "Apex Corp"
    assert ctx.company_size == "enterprise"


def test_tier1_keyword_fills_industry_gap() -> None:
    """ExtractionResult has no domain_hints; keyword scan detects industry."""
    er = _make_extraction(domain_hints=[])
    history = [{"role": "user", "content": "We handle litigation and court filings."}]
    ctx = extract_user_context(_make_state(extraction_result=er, history=history))["user_context"]
    assert ctx.industry_detail is not None
    assert "legal" in ctx.industry_detail.lower() or "law" in ctx.industry_detail.lower()


# ---------------------------------------------------------------------------
# preselected_intent integration
# ---------------------------------------------------------------------------


def test_preselected_intent_sets_methodology_when_hints_empty() -> None:
    er = _make_extraction(workflow_hints=[])
    ctx = extract_user_context(
        _make_state(extraction_result=er, preselected_intent="agile sprints")
    )["user_context"]
    assert ctx.work_methodology == "agile"


def test_preselected_intent_non_methodology_appended_to_key_phrases() -> None:
    er = _make_extraction()
    ctx = extract_user_context(
        _make_state(extraction_result=er, preselected_intent="onboarding")
    )["user_context"]
    assert "onboarding" in ctx.key_phrases


def test_preselected_intent_in_tier2_appended_to_key_phrases() -> None:
    """No ExtractionResult — preselected_intent should still surface in key_phrases."""
    history = [{"role": "user", "content": "We need help managing our team."}]
    ctx = extract_user_context(
        _make_state(preselected_intent="employee_records", history=history)
    )["user_context"]
    assert "employee_records" in ctx.key_phrases


def test_preselected_intent_methodology_not_duplicated_in_phrases() -> None:
    """A methodology-type intent should set work_methodology, not pollute key_phrases."""
    er = _make_extraction(workflow_hints=[])
    ctx = extract_user_context(
        _make_state(extraction_result=er, preselected_intent="kanban")
    )["user_context"]
    assert ctx.work_methodology == "kanban"
    assert "kanban" not in ctx.key_phrases


# ---------------------------------------------------------------------------
# Tier 2 — no ExtractionResult, history present (keyword path unchanged)
# ---------------------------------------------------------------------------


def test_tier2_extracts_company_name_from_history() -> None:
    history = [{"role": "user", "content": "We are Acme Corp and we need project tracking."}]
    ctx = extract_user_context(_make_state(history=history))["user_context"]
    assert ctx.company_name is not None


def test_tier2_detects_industry_from_history() -> None:
    history = [{"role": "user", "content": "We handle sprints and backlog grooming."}]
    ctx = extract_user_context(_make_state(history=history))["user_context"]
    assert ctx.industry_detail is not None


def test_tier2_returns_valid_user_context_shape() -> None:
    history = [{"role": "user", "content": "Small team of 10 doing agile development."}]
    ctx = extract_user_context(_make_state(history=history))["user_context"]
    assert ctx.company_size is not None
    assert ctx.work_methodology is not None
    assert len(ctx.work_items) > 0


# ---------------------------------------------------------------------------
# Tier 3 — nothing available
# ---------------------------------------------------------------------------


def test_tier3_returns_empty_user_context() -> None:
    ctx = extract_user_context(_make_state())["user_context"]
    assert ctx.company_name is None
    assert ctx.company_size is None
    assert ctx.teams == []
    assert ctx.people == []
    assert ctx.key_phrases == []
