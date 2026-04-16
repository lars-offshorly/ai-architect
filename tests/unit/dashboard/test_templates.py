"""Unit tests for dashboard/templates.py — DashboardTemplateRegistry."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from agents.preview_generator.dashboard.templates import (
    DashboardTemplateRegistry,
    _BUNDLE_TO_TEMPLATE,
)

_SAMPLE_TEMPLATE = {
    "dashboard_name": "Sample Template",
    "source": "analytics",
    "report": "Sample report text.",
    "widgets": [
        {
            "type": "number",
            "name": "Total Count",
            "calculation": {"datasets": [], "expected_value": "0"},
        }
    ],
}


@pytest.fixture
def templates_dir(tmp_path: Path) -> Path:
    """Write all templates referenced by _BUNDLE_TO_TEMPLATE into a temp dir."""
    filenames = set(_BUNDLE_TO_TEMPLATE.values())
    for filename in filenames:
        template = dict(_SAMPLE_TEMPLATE)
        template["dashboard_name"] = f"{filename} Template"
        (tmp_path / f"{filename}.json").write_text(json.dumps(template))
    return tmp_path


@pytest.fixture
def registry(templates_dir: Path) -> DashboardTemplateRegistry:
    return DashboardTemplateRegistry(templates_dir=templates_dir)


# ---------------------------------------------------------------------------
# Resolution — known bundles
# ---------------------------------------------------------------------------


def test_hr_management_returns_template(registry: DashboardTemplateRegistry):
    result = registry.get("hr_management")
    assert result is not None
    assert isinstance(result, dict)
    assert "dashboard_name" in result


def test_hr_hub_alias_resolves_same_as_hr_management(registry: DashboardTemplateRegistry):
    hr_management = registry.get("hr_management")
    hr_hub = registry.get("hr_hub")
    assert hr_management is not None
    assert hr_hub is not None
    assert hr_management["dashboard_name"] == hr_hub["dashboard_name"]


def test_project_mgmt_returns_template(registry: DashboardTemplateRegistry):
    result = registry.get("project_mgmt")
    assert result is not None
    assert "widgets" in result


# ---------------------------------------------------------------------------
# Resolution — unknown / Tier 3 bundles
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bundle_key",
    ["finance", "marketing", "sales", "unknown_bundle"],
)
def test_tier3_bundles_return_none(bundle_key: str, registry: DashboardTemplateRegistry):
    result = registry.get(bundle_key)
    assert result is None


# ---------------------------------------------------------------------------
# Deep copy — mutations don't affect the cache
# ---------------------------------------------------------------------------


def test_get_returns_deep_copy(registry: DashboardTemplateRegistry):
    copy1 = registry.get("hr_management")
    assert copy1 is not None
    copy1["dashboard_name"] = "MUTATED"

    copy2 = registry.get("hr_management")
    assert copy2 is not None
    assert copy2["dashboard_name"] != "MUTATED"


def test_mutating_widgets_does_not_affect_cache(registry: DashboardTemplateRegistry):
    copy1 = registry.get("project_mgmt")
    assert copy1 is not None
    copy1["widgets"].append({"type": "extra"})

    copy2 = registry.get("project_mgmt")
    assert copy2 is not None
    original_length = len(_SAMPLE_TEMPLATE["widgets"])
    assert len(copy2["widgets"]) == original_length


# ---------------------------------------------------------------------------
# Missing / invalid files
# ---------------------------------------------------------------------------


def test_missing_file_logs_warning_and_returns_none(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
):
    import logging

    with caplog.at_level(logging.WARNING):
        registry = DashboardTemplateRegistry(templates_dir=tmp_path)

    result = registry.get("hr_management")
    assert result is None
    assert any("not found" in rec.message for rec in caplog.records)


def test_invalid_json_logs_warning_and_returns_none(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
):
    import logging

    (tmp_path / "hr_management.json").write_text("{ invalid json }")

    with caplog.at_level(logging.WARNING):
        registry = DashboardTemplateRegistry(templates_dir=tmp_path)

    result = registry.get("hr_management")
    assert result is None


# ---------------------------------------------------------------------------
# supported_bundles
# ---------------------------------------------------------------------------


def test_supported_bundles_contains_known_keys(registry: DashboardTemplateRegistry):
    supported = registry.supported_bundles()
    assert "hr_management" in supported
    assert "hr_hub" in supported
    assert "project_mgmt" in supported


def test_supported_bundles_does_not_contain_tier3(registry: DashboardTemplateRegistry):
    supported = registry.supported_bundles()
    assert "finance" not in supported
    assert "marketing" not in supported
    assert "sales" not in supported
