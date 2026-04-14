"""Unit tests for dashboard/personalizer.py — personalize_template()."""

from __future__ import annotations

import copy
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from agents.preview_generator.dashboard.personalizer import (
    _build_llm_human_message,
    personalize_template,
)
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


# ---------------------------------------------------------------------------
# LLM report generation — happy path
# ---------------------------------------------------------------------------

_HISTORY = [
    {"role": "user", "content": "We need to track our headcount at Acme Corp."},
    {"role": "assistant", "content": "Got it! Which departments?"},
    {"role": "user", "content": "Engineering and Sales mainly."},
]


def _mock_llm_response(text: str) -> MagicMock:
    response = MagicMock()
    response.content = text
    return response


def _mock_llm(text: str) -> MagicMock:
    llm = MagicMock()
    llm.invoke.return_value = _mock_llm_response(text)
    return llm


def test_llm_report_replaces_template_report():
    """When LLM returns text, the report field should use it."""
    template = _make_template(report="This is the Template report.")
    ctx = _ctx(company="Acme Corp")

    with patch(
        "agents.preview_generator.dashboard.personalizer.get_settings"
    ) as mock_settings, patch(
        "agents.preview_generator.dashboard.personalizer.get_openai_chat_model"
    ) as mock_get_llm:
        mock_settings.return_value.OPENAI_API_KEY = "sk-test"
        mock_settings.return_value.ASSEMBLER_TEMPERATURE = 0.2
        mock_get_llm.return_value = _mock_llm("Acme Corp tracks headcount across all teams.")

        result = personalize_template(template, ctx, "hr_management", _HISTORY)

    assert result["report"] == "Acme Corp tracks headcount across all teams."


def test_llm_report_strips_whitespace():
    """LLM output is stripped before being written to the payload."""
    template = _make_template(report="Template report.")
    ctx = _ctx(company="Globex")

    with patch(
        "agents.preview_generator.dashboard.personalizer.get_settings"
    ) as mock_settings, patch(
        "agents.preview_generator.dashboard.personalizer.get_openai_chat_model"
    ) as mock_get_llm:
        mock_settings.return_value.OPENAI_API_KEY = "sk-test"
        mock_settings.return_value.ASSEMBLER_TEMPERATURE = 0.2
        mock_get_llm.return_value = _mock_llm("  Globex dashboard report.  ")

        result = personalize_template(template, ctx, "hr_management", _HISTORY)

    assert result["report"] == "Globex dashboard report."


# ---------------------------------------------------------------------------
# LLM report generation — fallback paths
# ---------------------------------------------------------------------------


def test_llm_skipped_when_no_api_key():
    """With no OPENAI_API_KEY the keyword fallback is used — LLM never called."""
    template = _make_template(report="This is the Template report.")
    ctx = _ctx(company="Initech")

    with patch(
        "agents.preview_generator.dashboard.personalizer.get_settings"
    ) as mock_settings, patch(
        "agents.preview_generator.dashboard.personalizer.get_openai_chat_model"
    ) as mock_get_llm:
        mock_settings.return_value.OPENAI_API_KEY = ""
        result = personalize_template(template, ctx, "hr_management", _HISTORY)

    mock_get_llm.assert_not_called()
    assert "Initech" in result["report"]
    assert "Template" not in result["report"]


def test_llm_exception_falls_back_to_keyword():
    """If the LLM call raises, keyword substitution is used."""
    template = _make_template(report="This is the Template report.")
    ctx = _ctx(company="Umbrella")

    with patch(
        "agents.preview_generator.dashboard.personalizer.get_settings"
    ) as mock_settings, patch(
        "agents.preview_generator.dashboard.personalizer.get_openai_chat_model"
    ) as mock_get_llm:
        mock_settings.return_value.OPENAI_API_KEY = "sk-test"
        mock_settings.return_value.ASSEMBLER_TEMPERATURE = 0.2
        mock_get_llm.return_value.invoke.side_effect = RuntimeError("API down")

        result = personalize_template(template, ctx, "hr_management", _HISTORY)

    assert "Umbrella" in result["report"]
    assert "Template" not in result["report"]


def test_llm_empty_response_falls_back_to_keyword():
    """Empty LLM content triggers keyword fallback."""
    template = _make_template(report="This is the Template report.")
    ctx = _ctx(company="Cyberdyne")

    with patch(
        "agents.preview_generator.dashboard.personalizer.get_settings"
    ) as mock_settings, patch(
        "agents.preview_generator.dashboard.personalizer.get_openai_chat_model"
    ) as mock_get_llm:
        mock_settings.return_value.OPENAI_API_KEY = "sk-test"
        mock_settings.return_value.ASSEMBLER_TEMPERATURE = 0.2
        mock_get_llm.return_value = _mock_llm("")

        result = personalize_template(template, ctx, "hr_management", _HISTORY)

    assert "Cyberdyne" in result["report"]


def test_llm_no_history_still_calls_llm():
    """LLM is attempted even when conversation_history is empty."""
    template = _make_template(report="Template report.")
    ctx = _ctx(company="Weyland")

    with patch(
        "agents.preview_generator.dashboard.personalizer.get_settings"
    ) as mock_settings, patch(
        "agents.preview_generator.dashboard.personalizer.get_openai_chat_model"
    ) as mock_get_llm:
        mock_settings.return_value.OPENAI_API_KEY = "sk-test"
        mock_settings.return_value.ASSEMBLER_TEMPERATURE = 0.2
        mock_get_llm.return_value = _mock_llm("Weyland Corp dashboard.")

        result = personalize_template(template, ctx, "hr_management", conversation_history=[])

    assert result["report"] == "Weyland Corp dashboard."


# ---------------------------------------------------------------------------
# _build_llm_human_message
# ---------------------------------------------------------------------------


def test_build_llm_human_message_includes_company():
    ctx = _ctx(company="Initech", teams=["Engineering"])
    msg = _build_llm_human_message(ctx, "hr_management", _HISTORY, "Fallback report.")
    assert "Initech" in msg


def test_build_llm_human_message_includes_teams():
    ctx = _ctx(teams=["Sales", "HR"])
    msg = _build_llm_human_message(ctx, "hr_management", [], "Fallback.")
    assert "Sales" in msg
    assert "HR" in msg


def test_build_llm_human_message_includes_bundle():
    ctx = _ctx()
    msg = _build_llm_human_message(ctx, "project_mgmt", [], "Fallback.")
    assert "Project Mgmt" in msg


def test_build_llm_human_message_includes_conversation_excerpt():
    ctx = _ctx()
    msg = _build_llm_human_message(ctx, "hr_management", _HISTORY, "Fallback.")
    assert "headcount" in msg


def test_build_llm_human_message_caps_history_at_five():
    """Only the last 5 user messages should appear."""
    history = [{"role": "user", "content": f"Message {i}"} for i in range(10)]
    ctx = _ctx()
    msg = _build_llm_human_message(ctx, "hr_management", history, "Fallback.")
    # Only messages 5-9 should appear.
    assert "Message 9" in msg
    assert "Message 0" not in msg


def test_build_llm_human_message_no_context_still_builds():
    """None user_context should not raise."""
    msg = _build_llm_human_message(None, "ticketing", _HISTORY, "Fallback.")
    assert "Ticketing" in msg
    assert "Fallback." in msg
