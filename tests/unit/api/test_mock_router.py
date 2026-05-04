from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.mock import router as mock_router


class _FakePayload:
    def __init__(self, bundle_key: str) -> None:
        self.bundle_key = bundle_key
        self.generation_json = {"bundle_key": bundle_key, "modules": ["A"], "config": {}}
        self.dummy_data_json = {"bundle_key": bundle_key, "stores": {}}
        self.feature_flags = []
        self.permission_services = []
        self.landing_pages = []
        self.service_mocks = {}


class _FakeBuilder:
    known_bundle_keys = frozenset({"project_mgmt", "finance", "ticketing", "healthcare"})
    known_render_keys = frozenset({"legacy_project", "legacy_ticketing"})
    render_alias_map = {
        "legacy_project": ["finance", "project_mgmt"],
        "legacy_ticketing": ["healthcare", "ticketing"],
    }

    def build(self, bundle_key: str, dummy_data_override=None, session_id=None):
        return _FakePayload(bundle_key)

    def build_stores(self, bundle_key: str):
        return {"bundle_key": bundle_key, "stores": {}}

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


def test_mock_rejects_ambiguous_legacy_render_key() -> None:
    client = _client()
    res = client.post("/mock/legacy_project", json={})
    assert res.status_code == 400
    assert "Ambiguous legacy render key" in res.json()["detail"]
