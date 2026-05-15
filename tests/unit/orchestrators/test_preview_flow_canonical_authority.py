from __future__ import annotations

from types import SimpleNamespace

from orchestrators.preview_flow import PreviewFlow


class _Facade:
    def build_payload_stores(self, bundle_key: str, dummy_data_json: dict) -> bool:
        stores = dummy_data_json.setdefault("stores", {})
        stores["queues"] = [{"id": 999, "name": "Canonical Queue"}]
        stores["projects"] = [{"id": 888, "name": "Canonical Project"}]
        stores["kpis"] = [{"id": 777, "key": "canonical_kpi", "label": "Canonical KPI"}]
        stores["employees"] = [{"id": 1, "position": "Director", "team": "A", "department": "Ops", "job_title": "Director", "job_type": "Full-Time", "job_level": "Director"}]
        stores["request_types"] = [{"id": 801, "name": "Leave Request"}]
        stores["canonical_dashboards"] = [{"id": 701, "name": "Operations Overview"}]
        return True


class _TemplateLoader:
    def load(self, bundle_key: str, variant_key: str | None = None):
        return {
            "stores": {
                "queues": [{"id": "template-q", "name": "Template Queue"}],
                "projects": [{"id": "template-p", "name": "Template Project"}],
                "kpis": [{"id": "template-k", "key": "template", "label": "Template KPI"}],
                "employees": [{"id": "template-e"}],
                "request_types": [{"id": "template-r"}],
                "canonical_dashboards": [{"id": "template-d"}],
                "tickets": [{"id": "template-ticket"}],
            }
        }


def test_preview_flow_keeps_canonical_core_stores_authoritative() -> None:
    preview_service = SimpleNamespace(
        generate=lambda **kwargs: (
            {"modules": []},
            {"stores": {}},
            None,
        )
    )
    flow = PreviewFlow(
        preview_generator_service=preview_service,
        bundle_display_names={"ticketing": "Ticketing"},
        registry_facade=_Facade(),
        bundle_template_loader=_TemplateLoader(),
        static_dashboard_outputs=None,
    )

    payload = flow.run(
        session_id="s1",
        bundle_key="ticketing",
        conversation_history=[{"role": "user", "content": "hello"}],
    )

    stores = payload.dummy_data_json["stores"]
    assert stores["queues"][0]["id"] == 999
    assert stores["projects"][0]["id"] == 888
    assert stores["kpis"][0]["id"] == 777
    assert stores["employees"][0]["id"] == 1
    assert stores["request_types"][0]["id"] == 801
    assert stores["canonical_dashboards"][0]["id"] == 701
    # non-core stores may still be overlaid from template during transition
    assert stores["tickets"][0]["id"] == "template-ticket"
