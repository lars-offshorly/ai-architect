"""Unit tests for POST /sessions/{id}/preview/edit endpoint."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.routers.preview import router as preview_router
from domain.models.session import Session
from fastapi import FastAPI


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_app(session_repo, conv_repo) -> FastAPI:
    """Build a minimal FastAPI app with the preview router."""
    from api.deps import (
        get_session_repository,
        get_conversation_repository,
    )

    app = FastAPI()
    app.include_router(preview_router)
    app.dependency_overrides[get_session_repository] = lambda: session_repo
    app.dependency_overrides[get_conversation_repository] = lambda: conv_repo
    return app


def _make_preview_payload(session_id: str = "sess-1") -> dict:
    """Build a minimal preview payload for edit testing."""
    return {
        "schema_version": "1.0",
        "session_id": session_id,
        "bundle_key": "project_mgmt",
        "display_name": "Project Management",
        "modules": ["Projects", "Chat", "Dashboard", "KPI"],
        "generation_json": {
            "schema_version": "1.0",
            "bundle_key": "project_mgmt",
            "feature_flags": [
                {"id": 5, "name": "chat-module", "description": "Chat Module", "isEnabled": True, "module": "Global"},
                {"id": 7, "name": "projects-module", "description": "Projects Module", "isEnabled": True, "module": "Global"},
                {"id": 2, "name": "dashboard-module", "description": "Dashboard Module", "isEnabled": True, "module": "Global"},
                {"id": 123, "name": "kpi-module", "description": "KPI Module", "isEnabled": True, "module": "Global"},
            ],
            "modules": ["Projects", "Chat", "Dashboard", "KPI"],
            "config": {
                "permission_services": ["projects", "kpi"],
                "landing_pages": [],
                "kpi_definitions": ["capacity_utilization"],
            },
        },
        "dummy_data_json": {
            "bundle_key": "project_mgmt",
            "session_id": session_id,
            "company_name": "TestCo",
            "stores": {
                "kpis": [
                    {
                        "key": "capacity_utilization",
                        "label": "Capacity Utilization",
                        "type": "percentage",
                        "source_service": "hr_hub",
                        "sample_value": 87.5,
                    }
                ],
                "dashboard_widgets": [],
            },
        },
        "warning": None,
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


class FakeConvRepo:
    def get_messages(self, _session_id: str) -> list:
        return []

    def append_message(self, _session_id: str, _msg: object) -> None:
        pass


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEditEndpoint:
    def setup_method(self) -> None:
        self.session_repo = FakeSessionRepo()
        self.conv_repo = FakeConvRepo()
        self.app = _build_app(self.session_repo, self.conv_repo)
        self.client = TestClient(self.app)

        # Seed a session
        session = Session(session_id="sess-1", confirmed=True, selected_bundle_key="project_mgmt")
        self.session_repo.save(session)

    def test_successful_edit(self) -> None:
        resp = self.client.post(
            "/sessions/sess-1/preview/edit",
            json={
                "current_preview": _make_preview_payload(),
                "instruction": "remove the chat module",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "Chat" not in data["modules"]

    def test_session_not_found(self) -> None:
        resp = self.client.post(
            "/sessions/nonexistent/preview/edit",
            json={
                "current_preview": _make_preview_payload("nonexistent"),
                "instruction": "remove chat",
            },
        )
        assert resp.status_code == 404

    def test_unsupported_instruction_returns_warning(self) -> None:
        resp = self.client.post(
            "/sessions/sess-1/preview/edit",
            json={
                "current_preview": _make_preview_payload(),
                "instruction": "change the background to purple",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["warning"] is not None

    def test_preserves_session_id_and_bundle_key(self) -> None:
        resp = self.client.post(
            "/sessions/sess-1/preview/edit",
            json={
                "current_preview": _make_preview_payload(),
                "instruction": "add calendar",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == "sess-1"
        assert data["bundle_key"] == "project_mgmt"

    def test_add_kpi_via_endpoint(self) -> None:
        resp = self.client.post(
            "/sessions/sess-1/preview/edit",
            json={
                "current_preview": _make_preview_payload(),
                "instruction": "add SLA compliance KPI",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        kpi_keys = [k["key"] for k in data["dummy_data_json"]["stores"]["kpis"]]
        assert "sla_compliance" in kpi_keys

    def test_edit_response_schema_shape(self) -> None:
        """Verify the response has the expected top-level keys."""
        resp = self.client.post(
            "/sessions/sess-1/preview/edit",
            json={
                "current_preview": _make_preview_payload(),
                "instruction": "remove projects",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "schema_version" in data
        assert "generation_json" in data
        assert "dummy_data_json" in data
        assert "modules" in data
