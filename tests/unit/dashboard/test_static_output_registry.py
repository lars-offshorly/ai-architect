"""Unit tests for dashboard/static_output_registry.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.preview_generator.dashboard.static_output_registry import (
    StaticDashboardOutputRegistry,
)


def test_all_dashboard_output_templates_have_non_empty_widgets() -> None:
    output_dir = Path(__file__).resolve().parents[3] / "dashboard_output_templates"
    files = sorted(output_dir.glob("*.json"))
    assert files, "No dashboard output templates found"

    for file_path in files:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
        widgets = payload.get("widgets")
        assert isinstance(widgets, list), f"{file_path.name}: widgets must be a list"
        assert widgets, f"{file_path.name}: widgets must be non-empty"
        assert all(
            isinstance(widget, dict) for widget in widgets
        ), f"{file_path.name}: widgets must contain only objects"


def test_registry_skips_malformed_or_empty_widget_outputs(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    (tmp_path / "valid.json").write_text(
        json.dumps({"widgets": [{"id": "widget-1"}]}), encoding="utf-8"
    )
    (tmp_path / "bad-shape.json").write_text(
        json.dumps({"widgets": []}), encoding="utf-8"
    )
    (tmp_path / "bad-type.json").write_text(
        json.dumps({"widgets": [1, 2, 3]}), encoding="utf-8"
    )

    with caplog.at_level("WARNING"):
        registry = StaticDashboardOutputRegistry(output_dir=tmp_path)

    assert registry.get_widgets("any", "valid") is None
    assert registry._cache.get("valid") is not None  # pylint: disable=protected-access
    assert "bad-shape" not in registry._cache  # pylint: disable=protected-access
    assert "bad-type" not in registry._cache  # pylint: disable=protected-access
    assert "Invalid static dashboard output" in caplog.text
