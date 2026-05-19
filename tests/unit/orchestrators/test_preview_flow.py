"""Unit tests for static dashboard enrichment in PreviewFlow."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from agents.tenant_provisioning.service import TenantProvisioningError
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


# ---------------------------------------------------------------------------
# v2 manifest emission tests
# ---------------------------------------------------------------------------


def _v2_manifest_dict() -> dict[str, object]:
    return {
        "schema_version": "2.0",
        "session_id": "sess-v2",
        "generated_at": "2026-05-20T00:00:00Z",
        "tenant": {
            "company_name": "Acme",
            "industry": "Technology",
            "size_band": "mid-sized",
            "primary_region": "us-east-1",
            "locale": "en-US",
            "timezone": "America/New_York",
        },
        "tickets": {"queues": []},
        "projects": {"projects": []},
        "dashboard": {"dashboards": []},
        "kpi": {"kpis": []},
        "hr_hub": {"employees": [], "request_types": []},
    }


def _make_flow_with_provisioning(provisioning_service=None) -> PreviewFlow:
    preview_service = MagicMock()
    preview_service.generate.return_value = (
        {"modules": ["HR Hub"]},
        {"stores": {}},
        None,
    )
    return PreviewFlow(
        preview_generator_service=preview_service,
        bundle_display_names={"hr_hub": "HR Hub"},
        tenant_provisioning_service=provisioning_service,
    )


def test_run_populates_v2_manifest_when_provisioning_service_present() -> None:
    svc = MagicMock()
    svc.provision.return_value = _v2_manifest_dict()
    flow = _make_flow_with_provisioning(svc)

    payload = flow.run(
        session_id="sess-v2",
        bundle_key="hr_hub",
        conversation_history=[{"role": "user", "content": "I need HR tools"}],
    )

    assert payload.v2_manifest == _v2_manifest_dict()
    svc.provision.assert_called_once_with(
        bundle_key="hr_hub",
        user_message="I need HR tools",
        session_id="sess-v2",
    )


def test_run_sets_v2_manifest_none_when_provisioning_service_absent() -> None:
    flow = _make_flow_with_provisioning(None)
    payload = flow.run(
        session_id="sess-noprovisioning",
        bundle_key="hr_hub",
        conversation_history=[{"role": "user", "content": "hello"}],
    )
    assert payload.v2_manifest is None


def test_run_sets_v2_manifest_none_when_provisioning_raises(caplog) -> None:
    svc = MagicMock()
    svc.provision.side_effect = TenantProvisioningError("no manifest for bundle")
    flow = _make_flow_with_provisioning(svc)

    with caplog.at_level(logging.WARNING):
        payload = flow.run(
            session_id="sess-fail",
            bundle_key="unknown_bundle",
            conversation_history=[{"role": "user", "content": "help"}],
        )

    assert payload.v2_manifest is None
    assert "v2 manifest provisioning failed" in caplog.text


def test_last_user_message_extracted_from_history() -> None:
    svc = MagicMock()
    svc.provision.return_value = _v2_manifest_dict()
    flow = _make_flow_with_provisioning(svc)

    flow.run(
        session_id="sess-msg",
        bundle_key="hr_hub",
        conversation_history=[
            {"role": "assistant", "content": "How can I help?"},
            {"role": "user", "content": "I manage a team"},
            {"role": "assistant", "content": "Tell me more"},
            {"role": "user", "content": "We use HR Hub"},
        ],
    )

    svc.provision.assert_called_once_with(
        bundle_key="hr_hub",
        user_message="We use HR Hub",
        session_id="sess-msg",
    )


def test_run_passes_empty_string_when_no_user_message_in_history() -> None:
    svc = MagicMock()
    svc.provision.return_value = _v2_manifest_dict()
    flow = _make_flow_with_provisioning(svc)

    flow.run(
        session_id="sess-empty",
        bundle_key="hr_hub",
        conversation_history=[{"role": "assistant", "content": "Hello"}],
    )

    svc.provision.assert_called_once_with(
        bundle_key="hr_hub",
        user_message="",
        session_id="sess-empty",
    )
