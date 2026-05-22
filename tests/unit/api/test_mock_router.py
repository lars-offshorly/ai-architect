from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.mock import router as mock_router


class _FakePayload:
    def __init__(self, bundle_key: str) -> None:
        self.bundle_key = bundle_key
        self.manifest = {
            "schema_version": "2.0",
            "session_id": "sess-1",
            "generated_at": "2026-05-19T10:00:00Z",
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
        self.service_mocks = {}


class _FakeBuilder:
    known_bundle_keys = frozenset({"project_mgmt", "finance", "ticketing", "healthcare"})
    known_render_keys = frozenset({"alias_project", "alias_ticketing"})
    render_alias_map = {
        "alias_project": ["finance", "project_mgmt"],
        "alias_ticketing": ["healthcare", "ticketing"],
    }

    def build(self, bundle_key: str, manifest_override=None, session_id=None):
        return _FakePayload(bundle_key)

    def build_stores(self, bundle_key: str):
        return _FakePayload(bundle_key).manifest

    def build_flags(self, bundle_key: str):
        return [], [], []


def _client() -> TestClient:
    from api.deps import get_mock_payload_builder

    app = FastAPI()
    app.include_router(mock_router)
    app.dependency_overrides[get_mock_payload_builder] = lambda: _FakeBuilder()
    return TestClient(app)


def test_mock_accepts_canonical_bundle_key() -> None:
    client = _client()
    res = client.post("/mock/finance", json={})
    assert res.status_code == 200
    assert res.json()["bundle_key"] == "finance"


def test_mock_rejects_ambiguous_render_key() -> None:
    client = _client()
    res = client.post("/mock/alias_project", json={})
    assert res.status_code == 400
    assert "Ambiguous render key" in res.json()["detail"]
