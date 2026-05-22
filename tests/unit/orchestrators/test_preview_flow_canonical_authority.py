from __future__ import annotations

from types import SimpleNamespace

from orchestrators.preview_flow import PreviewFlow


class _TenantProvisioning:
    def provision(self, bundle_key: str, user_message: str, session_id: str) -> dict:
        return {
            "schema_version": "2.0",
            "session_id": session_id,
            "generated_at": "2026-05-21T00:00:00Z",
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


def test_preview_flow_keeps_canonical_core_stores_authoritative() -> None:
    preview_service = SimpleNamespace(
        generate=lambda **kwargs: (["Tickets"], None)
    )
    flow = PreviewFlow(
        preview_generator_service=preview_service,
        bundle_display_names={"ticketing": "Ticketing"},
        tenant_provisioning_service=_TenantProvisioning(),
    )

    payload = flow.run(
        session_id="s1",
        bundle_key="ticketing",
        conversation_history=[{"role": "user", "content": "hello"}],
    )

    assert payload.manifest["schema_version"] == "2.0"
    assert payload.modules == ["Tickets"]
