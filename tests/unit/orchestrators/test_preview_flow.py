"""Unit tests for static dashboard enrichment in PreviewFlow."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from orchestrators.preview_flow import PreviewFlow


def _flow_with_registry(registry: object | None) -> PreviewFlow:
    preview_service = MagicMock()
    preview_service.generate.return_value = ({}, {"stores": {}}, None)
    return PreviewFlow(
        preview_generator_service=preview_service,
        bundle_display_names={},
        static_dashboard_outputs=registry,  # type: ignore[arg-type]
    )


def _make_payload(widget_templates: list) -> dict:
    """Build a payload in the current dashboard-centric schema."""
    return {
        "widgets": [
            {
                "dashboard_external_id": 54,
                "name": "Projects Dashboard",
                "widget_templates": widget_templates,
            }
        ]
    }


def test_enriches_dashboard_widgets_from_static_output_when_available(caplog) -> None:
    widget_templates = [
        {"widget_template_external_id": 329, "name": "New Tasks"},
        {"widget_template_external_id": 328, "name": "Projects per Priority"},
    ]
    payload = _make_payload(widget_templates)
    registry = SimpleNamespace(get=MagicMock(return_value=payload))
    flow = _flow_with_registry(registry)
    dummy = {"stores": {}}

    with caplog.at_level(logging.INFO):
        flow._enrich_dashboard_widgets("s1", "hr_management", dummy, None, "app-01")

    # Widgets are coerced into app-generator canonical schema (id/type/title/position)
    widgets = dummy["stores"]["dashboard_widgets"]
    assert isinstance(widgets, list)
    assert len(widgets) == len(widget_templates)
    # Preserve order and names from the static payload
    assert [w["title"] for w in widgets] == [w["name"] for w in widget_templates]
    # Ensure required fields exist for app generator validation
    for w in widgets:
        assert "id" in w and w["id"]
        assert "type" in w and isinstance(w["type"], str)
        assert "position" in w and all(
            k in w["position"] for k in ("row", "col", "width", "height")
        )
    registry.get.assert_called_once_with("hr_management")
    assert "static dashboard output injected" in caplog.text


def test_logs_warning_and_returns_empty_widgets_when_static_output_missing(
    caplog,
) -> None:
    registry = SimpleNamespace(get=MagicMock(return_value=None))
    flow = _flow_with_registry(registry)
    dummy = {"stores": {}}

    with caplog.at_level(logging.WARNING):
        flow._enrich_dashboard_widgets("s1", "unknown_bundle", dummy, None, "app-01")

    assert dummy["stores"]["dashboard_widgets"] == []
    assert "no static dashboard output" in caplog.text


def test_logs_warning_and_returns_when_registry_not_initialized(caplog) -> None:
    flow = _flow_with_registry(None)
    dummy = {"stores": {}}

    with caplog.at_level(logging.WARNING):
        flow._enrich_dashboard_widgets("s1", "hr_management", dummy, None, "app-01")

    assert dummy["stores"]["dashboard_widgets"] == []
    assert "DashboardTemplateRegistry not initialized" in caplog.text


def test_does_not_call_any_http_client_during_dashboard_enrichment() -> None:
    widget_templates = [{"widget_template_external_id": 329, "name": "New Tasks"}]
    payload = _make_payload(widget_templates)
    registry = SimpleNamespace(get=MagicMock(return_value=payload))
    flow = _flow_with_registry(registry)
    dummy = {"stores": {}}

    with patch("httpx.post") as mock_post:
        flow._enrich_dashboard_widgets("s1", "hr_management", dummy, None, "app-01")

    mock_post.assert_not_called()
