"""Unit tests for dashboard/personalizer.py — personalize_template()."""

from __future__ import annotations

import copy
from datetime import date, timedelta

import pytest

from agents.preview_generator.dashboard.personalizer import personalize_template
from agents.preview_generator.schemas import TeamDetail, UserContext


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_template(**overrides) -> dict:
    base = {
        "dashboard_name": "HR Management Dashboard Template",
        "source": "analytics",
        "report": "This is the Template report for HR management.",
        "widgets": [
            {
                "type": "bar",
                "title": "Headcount by Department",
                "data_config": {
                    "module": "HR Hub",
                    "data_source": "employees",
                    "group_by": ["department"],
                    "fields": [],
                    "aggregation": "count",
                    "date_from": None,
                    "date_to": None,
                    "date_interval": None,
                },
            },
            {
                "type": "number",
                "name": "Total Employees",
                "calculation": {
                    "datasets": [{"data_source": "employees"}],
                    "expected_value": "0",
                },
            },
        ],
    }
    base.update(overrides)
    return base


def _ctx(
    company: str | None = None,
    teams: list[str] | None = None,
) -> UserContext:
    return UserContext(
        company_name=company,
        teams=[TeamDetail(name=t) for t in (teams or [])],
    )


# ---------------------------------------------------------------------------
# Original template is not mutated
# ---------------------------------------------------------------------------


def test_does_not_mutate_original_template():
    template = _make_template()
    original_name = template["dashboard_name"]
    personalize_template(template, _ctx(company="Acme"), "hr_management")
    assert template["dashboard_name"] == original_name


# ---------------------------------------------------------------------------
# dashboard_name personalisation
# ---------------------------------------------------------------------------


def test_template_word_replaced_by_company_name():
    template = _make_template(dashboard_name="HR Management Dashboard Template")
    result = personalize_template(template, _ctx(company="Acme Corp"), "hr_management")
    assert "Template" not in result["dashboard_name"]
    assert "Acme Corp" in result["dashboard_name"]


def test_company_name_appended_when_no_template_word():
    template = _make_template(dashboard_name="HR Management Dashboard")
    result = personalize_template(template, _ctx(company="Globex"), "hr_management")
    assert "Globex" in result["dashboard_name"]


def test_dashboard_name_unchanged_when_no_company():
    template = _make_template(dashboard_name="HR Management Dashboard Template")
    original = template["dashboard_name"]
    result = personalize_template(template, _ctx(), "hr_management")
    assert result["dashboard_name"] == original


def test_dashboard_name_unchanged_when_no_context():
    template = _make_template(dashboard_name="HR Management Dashboard Template")
    original = template["dashboard_name"]
    result = personalize_template(template, None, "hr_management")
    assert result["dashboard_name"] == original


# ---------------------------------------------------------------------------
# report personalisation
# ---------------------------------------------------------------------------


def test_template_word_in_report_replaced_by_company():
    template = _make_template(report="This is the Template report.")
    result = personalize_template(template, _ctx(company="Initech"), "hr_management")
    assert "Template" not in result["report"]
    assert "Initech" in result["report"]


def test_report_unchanged_when_no_company():
    template = _make_template(report="This is the Template report.")
    original = template["report"]
    result = personalize_template(template, _ctx(), "hr_management")
    assert result["report"] == original


# ---------------------------------------------------------------------------
# Date range defaults
# ---------------------------------------------------------------------------


def test_null_date_from_filled_with_last_12_months():
    template = _make_template()
    result = personalize_template(template, _ctx(), "hr_management")
    widget = result["widgets"][0]
    assert widget["data_config"]["date_from"] is not None
    expected = (date.today() - timedelta(days=365)).isoformat()
    assert widget["data_config"]["date_from"] == expected


def test_null_date_to_filled_with_today():
    template = _make_template()
    result = personalize_template(template, _ctx(), "hr_management")
    widget = result["widgets"][0]
    assert widget["data_config"]["date_to"] == date.today().isoformat()


def test_existing_date_from_not_overwritten():
    template = _make_template()
    template["widgets"][0]["data_config"]["date_from"] = "2023-01-01"
    result = personalize_template(template, _ctx(), "hr_management")
    assert result["widgets"][0]["data_config"]["date_from"] == "2023-01-01"


def test_existing_date_to_not_overwritten():
    template = _make_template()
    template["widgets"][0]["data_config"]["date_to"] = "2023-12-31"
    result = personalize_template(template, _ctx(), "hr_management")
    assert result["widgets"][0]["data_config"]["date_to"] == "2023-12-31"


def test_widget_without_data_config_not_affected():
    template = _make_template()
    # widgets[1] is a number widget with no data_config
    result = personalize_template(template, _ctx(), "hr_management")
    assert "data_config" not in result["widgets"][1]


# ---------------------------------------------------------------------------
# Team name substitution into fields[]
# ---------------------------------------------------------------------------


def test_empty_fields_filled_with_team_names():
    template = _make_template()
    ctx = _ctx(teams=["Engineering", "Sales", "HR"])
    result = personalize_template(template, ctx, "hr_management")
    assert result["widgets"][0]["data_config"]["fields"] == ["Engineering", "Sales", "HR"]


def test_non_empty_fields_not_replaced():
    template = _make_template()
    template["widgets"][0]["data_config"]["fields"] = ["Existing", "Departments"]
    ctx = _ctx(teams=["Engineering", "Sales"])
    result = personalize_template(template, ctx, "hr_management")
    assert result["widgets"][0]["data_config"]["fields"] == ["Existing", "Departments"]


def test_team_names_capped_at_six():
    template = _make_template()
    ctx = _ctx(teams=["A", "B", "C", "D", "E", "F", "G", "H"])
    result = personalize_template(template, ctx, "hr_management")
    assert len(result["widgets"][0]["data_config"]["fields"]) == 6


def test_no_team_names_fields_stay_empty():
    template = _make_template()
    ctx = _ctx(teams=[])
    result = personalize_template(template, ctx, "hr_management")
    assert result["widgets"][0]["data_config"]["fields"] == []


# ---------------------------------------------------------------------------
# No-op when user_context is None
# ---------------------------------------------------------------------------


def test_none_context_returns_valid_payload():
    template = _make_template()
    result = personalize_template(template, None, "hr_management")
    assert "dashboard_name" in result
    assert "widgets" in result
    # Dates should still be filled
    assert result["widgets"][0]["data_config"]["date_from"] is not None
    assert result["widgets"][0]["data_config"]["date_to"] is not None
