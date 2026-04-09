"""Unit tests for edit/parse.py — keyword-based instruction parser."""

from __future__ import annotations

from agents.preview_generator.edit.parse import parse_edit_instruction
from agents.preview_generator.schemas import EditActionType

# ---------------------------------------------------------------------------
# Remove module
# ---------------------------------------------------------------------------


def test_remove_module_chat() -> None:
    action = parse_edit_instruction("remove the chat module")
    assert action.action_type == EditActionType.REMOVE_MODULE
    assert action.target == "chat-module"


def test_remove_module_projects() -> None:
    action = parse_edit_instruction("remove projects")
    assert action.action_type == EditActionType.REMOVE_MODULE
    assert action.target == "projects-module"


def test_remove_module_tickets() -> None:
    action = parse_edit_instruction("disable the tickets module")
    assert action.action_type == EditActionType.REMOVE_MODULE
    assert action.target == "tickets-module"


def test_remove_module_hrhub_alias() -> None:
    """'hr hub' and 'hr' should both resolve to hrhub-module."""
    action = parse_edit_instruction("remove hr hub")
    assert action.action_type == EditActionType.REMOVE_MODULE
    assert action.target == "hrhub-module"


def test_remove_module_hr_short() -> None:
    action = parse_edit_instruction("disable hr")
    assert action.action_type == EditActionType.REMOVE_MODULE
    assert action.target == "hrhub-module"


def test_remove_module_weaves() -> None:
    action = parse_edit_instruction("hide the weaves module")
    assert action.action_type == EditActionType.REMOVE_MODULE
    assert action.target == "weaves-module"


def test_remove_module_calendar() -> None:
    action = parse_edit_instruction("drop calendar")
    assert action.action_type == EditActionType.REMOVE_MODULE
    assert action.target == "calendar_module"


def test_remove_module_ai_toolkit() -> None:
    action = parse_edit_instruction("remove AI toolkit")
    assert action.action_type == EditActionType.REMOVE_MODULE
    assert action.target == "ai-toolkit-module"


# ---------------------------------------------------------------------------
# Add module
# ---------------------------------------------------------------------------


def test_add_module_chat() -> None:
    action = parse_edit_instruction("add the chat module")
    assert action.action_type == EditActionType.ADD_MODULE
    assert action.target == "chat-module"


def test_add_module_calendar() -> None:
    action = parse_edit_instruction("enable calendar")
    assert action.action_type == EditActionType.ADD_MODULE
    assert action.target == "calendar_module"


def test_add_module_include() -> None:
    action = parse_edit_instruction("include projects module")
    assert action.action_type == EditActionType.ADD_MODULE
    assert action.target == "projects-module"


# ---------------------------------------------------------------------------
# Remove KPI
# ---------------------------------------------------------------------------


def test_remove_kpi_by_slug() -> None:
    action = parse_edit_instruction("remove the attendance_rate KPI")
    assert action.action_type == EditActionType.REMOVE_KPI
    assert action.target == "attendance_rate"


def test_remove_kpi_by_label() -> None:
    action = parse_edit_instruction("remove SLA Compliance metric")
    assert action.action_type == EditActionType.REMOVE_KPI
    assert action.target == "sla_compliance"


def test_remove_kpi_natural_language() -> None:
    action = parse_edit_instruction("disable the on time delivery rate KPI")
    assert action.action_type == EditActionType.REMOVE_KPI
    assert action.target == "on_time_delivery_rate"


# ---------------------------------------------------------------------------
# Add KPI
# ---------------------------------------------------------------------------


def test_add_kpi_by_slug() -> None:
    action = parse_edit_instruction("add cycle_time KPI")
    assert action.action_type == EditActionType.ADD_KPI
    assert action.target == "cycle_time"


def test_add_kpi_by_label() -> None:
    action = parse_edit_instruction("add Capacity Utilization metric")
    assert action.action_type == EditActionType.ADD_KPI
    assert action.target == "capacity_utilization"


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


def test_remove_dashboard() -> None:
    action = parse_edit_instruction("remove the dashboard")
    assert action.action_type == EditActionType.REMOVE_DASHBOARD
    assert action.target == "dashboard-module"


def test_add_dashboard() -> None:
    action = parse_edit_instruction("add a dashboard")
    assert action.action_type == EditActionType.ADD_DASHBOARD
    assert action.target == "dashboard-module"


# ---------------------------------------------------------------------------
# Unsupported
# ---------------------------------------------------------------------------


def test_unsupported_no_verb() -> None:
    action = parse_edit_instruction("the color should be blue")
    assert action.action_type == EditActionType.UNSUPPORTED


def test_unsupported_gibberish() -> None:
    action = parse_edit_instruction("asdf jkl;")
    assert action.action_type == EditActionType.UNSUPPORTED


def test_unsupported_empty() -> None:
    action = parse_edit_instruction("")
    assert action.action_type == EditActionType.UNSUPPORTED


# ---------------------------------------------------------------------------
# Case insensitivity
# ---------------------------------------------------------------------------


def test_case_insensitive_verb() -> None:
    action = parse_edit_instruction("REMOVE Chat")
    assert action.action_type == EditActionType.REMOVE_MODULE
    assert action.target == "chat-module"


def test_case_insensitive_target() -> None:
    action = parse_edit_instruction("Add PROJECTS")
    assert action.action_type == EditActionType.ADD_MODULE
    assert action.target == "projects-module"


# ---------------------------------------------------------------------------
# raw_instruction preserved
# ---------------------------------------------------------------------------


def test_raw_instruction_preserved() -> None:
    original = "Remove the chat module please"
    action = parse_edit_instruction(original)
    assert action.raw_instruction == original
