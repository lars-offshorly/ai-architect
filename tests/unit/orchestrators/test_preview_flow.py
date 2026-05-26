from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

from agents.tenant_provisioning.service import TenantProvisioningError
from core.exceptions import PreviewGenerationError
from orchestrators.preview_flow import PreviewFlow


def _manifest_dict() -> dict[str, object]:
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
    preview_service.generate.return_value = (["HR Hub"], None)
    return PreviewFlow(
        preview_generator_service=preview_service,
        bundle_display_names={"hr_hub": "HR Hub"},
        tenant_provisioning_service=provisioning_service,
    )


def test_run_populates_manifest_when_provisioning_service_present() -> None:
    svc = MagicMock()
    svc.provision.return_value = _manifest_dict()
    flow = _make_flow_with_provisioning(svc)

    payload = flow.run(
        session_id="sess-v2",
        bundle_key="hr_hub",
        conversation_history=[{"role": "user", "content": "I need HR tools"}],
    )

    assert payload.manifest == _manifest_dict()
    assert payload.modules == ["HR Hub"]
    svc.provision.assert_called_once_with(
        bundle_key="hr_hub",
        user_message="I need HR tools",
        session_id="sess-v2",
        tenant_overrides=None,
    )


def test_run_raises_when_provisioning_service_absent() -> None:
    flow = _make_flow_with_provisioning(None)
    with pytest.raises(PreviewGenerationError, match="manifest missing"):
        flow.run(
            session_id="sess-noprovisioning",
            bundle_key="hr_hub",
            conversation_history=[{"role": "user", "content": "hello"}],
        )


def test_run_raises_when_provisioning_raises(caplog) -> None:
    svc = MagicMock()
    svc.provision.side_effect = TenantProvisioningError("no manifest for bundle")
    flow = _make_flow_with_provisioning(svc)

    with caplog.at_level(logging.WARNING):
        with pytest.raises(PreviewGenerationError, match="manifest missing"):
            flow.run(
                session_id="sess-fail",
                bundle_key="unknown_bundle",
                conversation_history=[{"role": "user", "content": "help"}],
            )
    assert "manifest provisioning failed" in caplog.text
