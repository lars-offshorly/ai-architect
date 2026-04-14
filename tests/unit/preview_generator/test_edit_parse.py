"""Unit tests for edit/parse.py — keyword-based instruction parser."""

from __future__ import annotations

from pathlib import Path

import pytest

from agents.preview_generator.edit.parse import parse_edit_instruction
from agents.preview_generator.schemas import EditActionType
from catalog.bundle_catalog import BundleCatalog

REGISTRY_PATH = (
    Path(__file__).resolve().parents[3] / "src/templates/bundle_registry.yaml"
)


@pytest.fixture
def catalog() -> BundleCatalog:
    return BundleCatalog(REGISTRY_PATH)


# ---------------------------------------------------------------------------
# Remove module
# ---------------------------------------------------------------------------


def test_remove_module_chat(catalog: BundleCatalog) -> None:
    action = parse_edit_instruction("remove the chat module", catalog)
    assert action.action_type == EditActionType.REMOVE_MODULE
    assert action.target == "chat-module"


def test_remove_module_projects(catalog: BundleCatalog) -> None:
    action = parse_edit_instruction("remove projects", catalog)
    assert action.action_type == EditActionType.REMOVE_MODULE
    assert action.target == "projects-module"


def test_remove_module_tickets(catalog: BundleCatalog) -> None:
    action = parse_edit_instruction("disable the tickets module", catalog)
    assert action.action_type == EditActionType.REMOVE_MODULE
    assert action.target == "tickets-module"


def test_remove_module_hrhub_alias(catalog: BundleCatalog) -> None:
    """'hr hub' and 'hr' should both resolve to hrhub-module."""
    action = parse_edit_instruction("remove hr hub", catalog)
    assert action.action_type == EditActionType.REMOVE_MODULE
    assert action.target == "hrhub-module"


def test_remove_module_hr_short(catalog: BundleCatalog) -> None:
    action = parse_edit_instruction("disable hr", catalog)
    assert action.action_type == EditActionType.REMOVE_MODULE
    assert action.target == "hrhub-module"


def test_remove_module_weaves(catalog: BundleCatalog) -> None:
    action = parse_edit_instruction("hide the weaves module", catalog)
    assert action.action_type == EditActionType.REMOVE_MODULE
    assert action.target == "weaves-module"


def test_remove_module_calendar(catalog: BundleCatalog) -> None:
    action = parse_edit_instruction("drop calendar", catalog)
    assert action.action_type == EditActionType.REMOVE_MODULE
    assert action.target == "calendar_module"


def test_remove_module_ai_toolkit(catalog: BundleCatalog) -> None:
    action = parse_edit_instruction("remove AI toolkit", catalog)
    assert action.action_type == EditActionType.REMOVE_MODULE
    assert action.target == "ai-toolkit-module"


# ---------------------------------------------------------------------------
# Add module
# ---------------------------------------------------------------------------


def test_add_module_chat(catalog: BundleCatalog) -> None:
    action = parse_edit_instruction("add the chat module", catalog)
    assert action.action_type == EditActionType.ADD_MODULE
    assert action.target == "chat-module"


def test_add_module_calendar(catalog: BundleCatalog) -> None:
    action = parse_edit_instruction("enable calendar", catalog)
    assert action.action_type == EditActionType.ADD_MODULE
    assert action.target == "calendar_module"


def test_add_module_include(catalog: BundleCatalog) -> None:
    action = parse_edit_instruction("include projects module", catalog)
    assert action.action_type == EditActionType.ADD_MODULE
    assert action.target == "projects-module"


# ---------------------------------------------------------------------------
# Remove KPI
# ---------------------------------------------------------------------------


def test_remove_kpi_by_slug(catalog: BundleCatalog) -> None:
    action = parse_edit_instruction("remove the attendance_rate KPI", catalog)
    assert action.action_type == EditActionType.REMOVE_KPI
    assert action.target == "attendance_rate"


def test_remove_kpi_by_label(catalog: BundleCatalog) -> None:
    action = parse_edit_instruction("remove SLA Compliance metric", catalog)
    assert action.action_type == EditActionType.REMOVE_KPI
    assert action.target == "sla_compliance"


def test_remove_kpi_natural_language(catalog: BundleCatalog) -> None:
    action = parse_edit_instruction("disable the on time delivery rate KPI", catalog)
    assert action.action_type == EditActionType.REMOVE_KPI
    assert action.target == "on_time_delivery_rate"


# ---------------------------------------------------------------------------
# Add KPI
# ---------------------------------------------------------------------------


def test_add_kpi_by_slug(catalog: BundleCatalog) -> None:
    action = parse_edit_instruction("add cycle_time KPI", catalog)
    assert action.action_type == EditActionType.ADD_KPI
    assert action.target == "cycle_time"


def test_add_kpi_by_label(catalog: BundleCatalog) -> None:
    action = parse_edit_instruction("add Capacity Utilization metric", catalog)
    assert action.action_type == EditActionType.ADD_KPI
    assert action.target == "capacity_utilization"


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


def test_remove_dashboard(catalog: BundleCatalog) -> None:
    action = parse_edit_instruction("remove the dashboard", catalog)
    assert action.action_type == EditActionType.REMOVE_DASHBOARD
    assert action.target == "dashboard-module"


def test_add_dashboard(catalog: BundleCatalog) -> None:
    action = parse_edit_instruction("add a dashboard", catalog)
    assert action.action_type == EditActionType.ADD_DASHBOARD
    assert action.target == "dashboard-module"


# ---------------------------------------------------------------------------
# Unsupported
# ---------------------------------------------------------------------------


def test_unsupported_no_verb(catalog: BundleCatalog) -> None:
    action = parse_edit_instruction("the color should be blue", catalog)
    assert action.action_type == EditActionType.UNSUPPORTED


def test_unsupported_gibberish(catalog: BundleCatalog) -> None:
    action = parse_edit_instruction("asdf jkl;", catalog)
    assert action.action_type == EditActionType.UNSUPPORTED


def test_unsupported_empty(catalog: BundleCatalog) -> None:
    action = parse_edit_instruction("", catalog)
    assert action.action_type == EditActionType.UNSUPPORTED


# ---------------------------------------------------------------------------
# Case insensitivity
# ---------------------------------------------------------------------------


def test_case_insensitive_verb(catalog: BundleCatalog) -> None:
    action = parse_edit_instruction("REMOVE Chat", catalog)
    assert action.action_type == EditActionType.REMOVE_MODULE
    assert action.target == "chat-module"


def test_case_insensitive_target(catalog: BundleCatalog) -> None:
    action = parse_edit_instruction("Add PROJECTS", catalog)
    assert action.action_type == EditActionType.ADD_MODULE
    assert action.target == "projects-module"


# ---------------------------------------------------------------------------
# raw_instruction preserved
# ---------------------------------------------------------------------------


def test_raw_instruction_preserved(catalog: BundleCatalog) -> None:
    original = "Remove the chat module please"
    action = parse_edit_instruction(original, catalog)
    assert action.raw_instruction == original
