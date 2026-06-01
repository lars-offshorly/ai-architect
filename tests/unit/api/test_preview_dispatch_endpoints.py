"""Unit tests for preview endpoint dispatch to BE translator."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.preview import router as preview_router
from domain.models.app_payload import AppPayload
from domain.models.session import Session


@dataclass
class _Message:
    role: str
    content: str


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
    def get_messages(self, _session_id: str) -> list[_Message]:
        return [_Message(role="user", content="Build helpdesk system")]


class FakeTranslatorClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def translate_preview(self, **kwargs: object) -> dict:
        self.calls.append(dict(kwargs))
        return {"status": "accepted"}


class FakePreviewFlow:
    def run(
        self,
        session_id: str,
        bundle_key: str,
        conversation_history: list[dict],
        extraction_result: object | None = None,
        preselected_intent: str | None = None,
    ) -> AppPayload:
        _ = conversation_history
        _ = extraction_result
        _ = preselected_intent
        return AppPayload(
            schema_version="2.0",
            session_id=session_id,
            bundle_key=bundle_key,
            display_name="Project Management",
            modules=["Projects", "Dashboard"],
            manifest={
                "schema_version": "2.0",
                "session_id": session_id,
                "generated_at": "2026-05-21T10:00:00Z",
                "tenant": {
                    "company_name": "TestCo",
                    "industry": "project_mgmt",
                    "size_band": "11-50",
                    "primary_region": "APAC",
                    "locale": "en-PH",
                    "timezone": "Asia/Manila",
                },
                "tickets": {"queues": []},
                "projects": {"projects": []},
                "dashboard": {"dashboards": []},
                "kpi": {"kpis": []},
                "hr_hub": {"employees": [], "request_types": []},
            },
        )


class FakeRegistryFacade:
    def has_bundle(self, _bundle_key: str) -> bool:
        return True


class FakeBundleCatalog:
    def has_bundle(self, _bundle_key: str) -> bool:
        return True


def _build_app(
    session_repo: FakeSessionRepo,
    conv_repo: FakeConvRepo,
    preview_flow: FakePreviewFlow,
    translator_client: FakeTranslatorClient,
) -> FastAPI:
    from api.deps import (
        get_be_translator_client,
        get_bundle_catalog,
        get_conversation_repository,
        get_preview_flow,
        get_registry_facade,
        get_session_repository,
    )

    app = FastAPI()
    app.include_router(preview_router)
    app.dependency_overrides[get_session_repository] = lambda: session_repo
    app.dependency_overrides[get_conversation_repository] = lambda: conv_repo
    app.dependency_overrides[get_preview_flow] = lambda: preview_flow
    app.dependency_overrides[get_registry_facade] = lambda: FakeRegistryFacade()
    app.dependency_overrides[get_bundle_catalog] = lambda: FakeBundleCatalog()
    app.dependency_overrides[get_be_translator_client] = lambda: translator_client
    return app


class TestPreviewDispatchEndpoints:
    def setup_method(self) -> None:
        self.session_repo = FakeSessionRepo()
        self.conv_repo = FakeConvRepo()
        self.preview_flow = FakePreviewFlow()
        self.translator = FakeTranslatorClient()
        self.app = _build_app(
            self.session_repo,
            self.conv_repo,
            self.preview_flow,
            self.translator,
        )
        self.client = TestClient(self.app)
        self.session_repo.save(
            Session(
                session_id="sess-1",
                confirmed=True,
                selected_bundle_key="project_mgmt",
            )
        )

    def test_preview_dispatches_create_with_wrapped_preview_json(self) -> None:
        response = self.client.post("/sessions/sess-1/preview")
        assert response.status_code == 200
        assert len(self.translator.calls) == 1

        call = self.translator.calls[0]
        assert call["operation"] == "create"
        assert call["revision"] == 1
        assert call["document_id"] == "sess-1"

        wrapper = call["preview_json"]
        assert wrapper["documentId"] == "sess-1"
        assert wrapper["operation"] == "create"
        assert wrapper["revision"] == 1
        assert wrapper["previewJson"]["session_id"] == "sess-1"
        assert wrapper["previewJson"]["schema_version"] == "2.0"

    def test_early_preview_dispatches_create_and_increments_revision(self) -> None:
        first = self.client.post("/sessions/sess-1/preview")
        assert first.status_code == 200

        second = self.client.post("/sessions/sess-1/preview/early")
        assert second.status_code == 200
        assert len(self.translator.calls) == 2

        first_call = self.translator.calls[0]
        second_call = self.translator.calls[1]
        assert first_call["revision"] == 1
        assert second_call["revision"] == 2
        assert second_call["operation"] == "create"
        assert second_call["preview_json"]["previewJson"]["preview_type"] == "early"
