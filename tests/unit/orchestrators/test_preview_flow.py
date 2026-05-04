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


def test_enriches_dashboard_widgets_from_static_output_when_available(caplog) -> None:
    widgets = [{"id": "widget-1", "type": "number", "title": "A", "position": {}}]
    registry = SimpleNamespace(get_widgets=MagicMock(return_value=widgets))
    flow = _flow_with_registry(registry)
    dummy = {"stores": {}}

    with caplog.at_level(logging.INFO):
        flow._enrich_dashboard_widgets("s1", "hr_management", dummy, None, "app-01")

    assert dummy["stores"]["dashboard_widgets"] == widgets
    dashboard_output = dummy["stores"].get("dashboard_generation_output")
    assert isinstance(dashboard_output, dict)
    assert dashboard_output["widgets"]["total"] == len(widgets)
    registry.get_widgets.assert_called_once_with("hr_management", "app-01")
    assert "static dashboard output injected" in caplog.text


def test_logs_warning_and_returns_empty_widgets_when_static_output_missing(
    caplog,
) -> None:
    registry = SimpleNamespace(get_widgets=MagicMock(return_value=None))
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
    assert "StaticDashboardOutputRegistry not initialized" in caplog.text


def test_does_not_call_any_http_client_during_dashboard_enrichment() -> None:
    widgets = [{"id": "widget-1", "type": "number", "title": "A", "position": {}}]
    registry = SimpleNamespace(get_widgets=MagicMock(return_value=widgets))
    flow = _flow_with_registry(registry)
    dummy = {"stores": {}}

    with patch("httpx.post") as mock_post:
        flow._enrich_dashboard_widgets("s1", "hr_management", dummy, None, "app-01")

    mock_post.assert_not_called()
