"""Unit tests for POST /sessions/{id}/app — manifest-only contract."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.app import router as app_router
from domain.models.session import Session
from repositories.conversation_repository import ConversationRepository
from repositories.session_repository import SessionRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_app(
    session_repo: SessionRepository,
    registry_facade,
) -> FastAPI:
    from api.deps import get_registry_facade, get_session_repository

    app = FastAPI()
    app.include_router(app_router)
    app.dependency_overrides[get_session_repository] = lambda: session_repo
    app.dependency_overrides[get_registry_facade] = lambda: registry_facade
    return app


def _valid_manifest(session_id: str = "sess-1") -> dict:
    return {
        "schema_version": "2.0",
        "session_id": session_id,
        "generated_at": "2026-05-22T00:00:00Z",
        "tenant": {
            "company_name": "Acme Corp",
            "industry": "bpo_contact_center",
            "size_band": "50-200",
            "primary_region": "APAC",
            "locale": "en-PH",
            "timezone": "Asia/Manila",
        },
        "tickets": {"queues": [{"id": 1, "name": "Support"}]},
        "projects": {"projects": [{"id": 1, "name": "Alpha"}]},
        "dashboard": {"dashboards": [{"id": 1, "name": "Ops"}]},
        "kpi": {"kpis": [{"id": 1, "name": "ART"}]},
        "hr_hub": {
            "employees": [
                {
                    "id": 1,
                    "position": "Director",
                    "team": "Operations",
                    "department": "Operations",
                    "job_title": "Director",
                    "job_type": "Full-Time",
                    "job_level": "Director",
                }
            ],
            "request_types": [{"id": 1, "name": "Leave Request"}],
        },
    }


class FakeSessionRepo:
    def __init__(self) -> None:
        self._store: dict[str, Session] = {}

    def save(self, session: Session) -> None:
        self._store[session.session_id] = session

    def get(self, session_id: str) -> Session:
        from core.exceptions import SessionNotFoundError

        if session_id not in self._store:
            raise SessionNotFoundError(f"Session {session_id} not found")
        return self._store[session_id]


class FakeRegistryFacade:
    def __init__(self, *, has_bundle: bool = True) -> None:
        self._has_bundle = has_bundle

    def has_bundle(self, bundle_key: str) -> bool:
        return self._has_bundle


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAppRouterManifest:
    def setup_method(self) -> None:
        self.session_repo = FakeSessionRepo()
        self.registry = FakeRegistryFacade()
        self.app = _build_app(self.session_repo, self.registry)
        self.client = TestClient(self.app)

        self.session_repo.save(
            Session(session_id="sess-1", confirmed=True, selected_bundle_key="ticketing")
        )

    def test_happy_path_returns_200_with_manifest(self) -> None:
        manifest = _valid_manifest()
        resp = self.client.post("/sessions/sess-1/app", json={"manifest": manifest})
        assert resp.status_code == 200
        data = resp.json()
        assert data["manifest"] == manifest
        assert data["session_id"] == "sess-1"
        assert data["bundle_key"] == "ticketing"
        assert data["schema_version"] == "2.0"

    def test_malformed_manifest_returns_422(self) -> None:
        resp = self.client.post("/sessions/sess-1/app", json={"manifest": {}})
        assert resp.status_code == 422

    def test_session_not_found_returns_404(self) -> None:
        resp = self.client.post(
            "/sessions/unknown-sess/app", json={"manifest": _valid_manifest()}
        )
        assert resp.status_code == 404

    def test_unconfirmed_session_returns_400(self) -> None:
        self.session_repo.save(
            Session(session_id="sess-unconfirmed", confirmed=False, selected_bundle_key="ticketing")
        )
        resp = self.client.post(
            "/sessions/sess-unconfirmed/app", json={"manifest": _valid_manifest()}
        )
        assert resp.status_code == 400

    def test_bundle_not_in_registry_returns_404(self) -> None:
        app = _build_app(self.session_repo, FakeRegistryFacade(has_bundle=False))
        client = TestClient(app)
        resp = client.post("/sessions/sess-1/app", json={"manifest": _valid_manifest()})
        assert resp.status_code == 404
