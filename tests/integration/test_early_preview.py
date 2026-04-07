"""Integration tests: early preview endpoint and force_preview flag.

Layer 1 — Direct endpoint tests (pre-seeded session state)
  Verifies /preview/early behavior across session states: selected bundle,
  latest_classification only, and no bundle at all (fallback).

Layer 2 — Reply with force_preview flag
  Verifies that force_preview=True is passed through the API and the flow
  returns a warning and preview_type="early" in the response.
"""

from __future__ import annotations

import importlib
import os
import sys
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from api import deps
from api.deps import (
    get_conversation_repository,
    get_session_repository,
)
from domain.models.conversation import ConversationMessage
from domain.models.extraction_result import ExtractionResult
from domain.models.session import Session


@pytest.fixture(name="app", scope="module")
def fixture_app():
    sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
    os.environ["DEBUG"] = "True"
    config_module = importlib.import_module("core.config")
    config_module.get_settings.cache_clear()
    main_module = importlib.import_module("main")
    return main_module.create_app()


@pytest.fixture(name="client")
async def fixture_client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


def _unique_id() -> str:
    return str(uuid.uuid4())


def _seed_session(
    session_id: str,
    *,
    confirmed: bool = False,
    selected_bundle_key: str | None = None,
    latest_classification: dict | None = None,
    history: list[tuple[str, str]] | None = None,
) -> None:
    session_repo = get_session_repository()
    conv_repo = get_conversation_repository()

    session = Session(
        session_id=session_id,
        confirmed=confirmed,
        selected_bundle_key=selected_bundle_key,
        latest_classification=latest_classification,
    )
    session_repo.save(session)

    for role, content in history or []:
        conv_repo.append_message(
            session_id,
            ConversationMessage(role=role, content=content),  # type: ignore[arg-type]
        )


# ===========================================================================
# Layer 1 — /preview/early direct endpoint tests
# ===========================================================================


class TestEarlyPreviewEndpoint:
    @pytest.mark.asyncio
    async def test_early_preview_with_selected_bundle_returns_200(
        self, client: AsyncClient
    ) -> None:
        sid = _unique_id()
        _seed_session(sid, selected_bundle_key="hr_management")

        resp = await client.post(f"/sessions/{sid}/preview/early")
        assert resp.status_code == 200, resp.text

    @pytest.mark.asyncio
    async def test_early_preview_includes_warning_field(
        self, client: AsyncClient
    ) -> None:
        sid = _unique_id()
        _seed_session(sid, selected_bundle_key="hr_management")

        data = (await client.post(f"/sessions/{sid}/preview/early")).json()
        assert data["warning"] is not None
        assert "incomplete" in data["warning"].lower()

    @pytest.mark.asyncio
    async def test_early_preview_unconfirmed_session_still_returns_200(
        self, client: AsyncClient
    ) -> None:
        sid = _unique_id()
        _seed_session(sid, confirmed=False, selected_bundle_key="ticketing")

        resp = await client.post(f"/sessions/{sid}/preview/early")
        assert resp.status_code == 200, resp.text

    @pytest.mark.asyncio
    async def test_early_preview_uses_latest_classification_when_no_selected_bundle(
        self, client: AsyncClient
    ) -> None:
        sid = _unique_id()
        _seed_session(
            sid,
            latest_classification={"top_bundle_key": "project_mgmt"},
        )

        data = (await client.post(f"/sessions/{sid}/preview/early")).json()
        assert data["bundle_key"] == "project_mgmt"

    @pytest.mark.asyncio
    async def test_early_preview_falls_back_to_all_microservices_when_no_bundle(
        self, client: AsyncClient
    ) -> None:
        sid = _unique_id()
        _seed_session(sid)

        data = (await client.post(f"/sessions/{sid}/preview/early")).json()
        assert data["bundle_key"] == "all_microservices"
        assert data["warning"] is not None

    @pytest.mark.asyncio
    async def test_early_preview_missing_session_returns_404(
        self, client: AsyncClient
    ) -> None:
        resp = await client.post(f"/sessions/{_unique_id()}/preview/early")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_early_preview_response_has_required_schema_fields(
        self, client: AsyncClient
    ) -> None:
        sid = _unique_id()
        _seed_session(sid, selected_bundle_key="hr_management")

        data = (await client.post(f"/sessions/{sid}/preview/early")).json()
        assert data["schema_version"] == "1.0"
        assert data["session_id"] == sid
        assert data["bundle_key"] == "hr_management"
        assert data["display_name"] == "HR Management"
        assert isinstance(data["modules"], list)
        assert isinstance(data["generation_json"], dict)
        assert isinstance(data["dummy_data_json"], dict)

    @pytest.mark.asyncio
    async def test_regular_preview_still_requires_confirmation(
        self, client: AsyncClient
    ) -> None:
        """Verify that the standard /preview endpoint is unaffected."""
        sid = _unique_id()
        _seed_session(sid, confirmed=False, selected_bundle_key="ticketing")

        resp = await client.post(f"/sessions/{sid}/preview")
        assert resp.status_code == 400


# ===========================================================================
# Layer 2 — force_preview flag via /reply
# ===========================================================================


class TestForcePreviawViaReply:
    def _make_mock_flow(self, responses: list[dict]) -> object:
        """Return a mock ConversationFlow that yields from the given response list."""
        call_index = 0

        async def _process_turn(*_args: Any, **_kwargs: Any) -> dict:
            nonlocal call_index
            result = responses[min(call_index, len(responses) - 1)]
            call_index += 1
            return result

        mock = MagicMock()
        mock.process_turn = _process_turn
        return mock

    @pytest.mark.asyncio
    async def test_force_preview_true_returns_warning_in_reply(
        self, app: Any, client: AsyncClient
    ) -> None:
        mock_flow = self._make_mock_flow(
            [
                {
                    "status": "ready_for_preview",
                    "bundle_key": "hr_management",
                    "extracted": ExtractionResult(session_id="placeholder"),
                    "suggested": None,
                    "slots": {},
                    "warning": (
                        "Preview generated with incomplete information."
                        " Some data may be generic."
                    ),
                    "preview_type": "early",
                }
            ]
        )
        app.dependency_overrides[deps.get_conversation_flow] = lambda: mock_flow

        try:
            start_resp = await client.post(
                "/sessions",
                json={"message": "I need something"},
            )
            assert start_resp.status_code == 201
            sid = start_resp.json()["session_id"]

            reply_resp = await client.post(
                f"/sessions/{sid}/reply",
                json={"message": "just show me", "force_preview": True},
            )
            assert reply_resp.status_code == 200
            data = reply_resp.json()
            assert data["status"] == "ready_for_preview"
            assert data["warning"] is not None
            assert data["preview_type"] == "early"
        finally:
            app.dependency_overrides.pop(deps.get_conversation_flow, None)

    @pytest.mark.asyncio
    async def test_preview_keyword_in_message_surfaces_warning(
        self, app: Any, client: AsyncClient
    ) -> None:
        mock_flow = self._make_mock_flow(
            [
                {
                    "status": "ready_for_preview",
                    "bundle_key": "ticketing",
                    "extracted": ExtractionResult(session_id="placeholder"),
                    "suggested": None,
                    "slots": {},
                    "warning": (
                        "Preview generated with incomplete information."
                        " Some data may be generic."
                    ),
                    "preview_type": "early",
                }
            ]
        )
        app.dependency_overrides[deps.get_conversation_flow] = lambda: mock_flow

        try:
            start_resp = await client.post(
                "/sessions",
                json={"message": "I manage support tickets"},
            )
            assert start_resp.status_code == 201
            sid = start_resp.json()["session_id"]

            reply_resp = await client.post(
                f"/sessions/{sid}/reply",
                json={"message": "preview now"},
            )
            assert reply_resp.status_code == 200
            data = reply_resp.json()
            assert data["status"] == "ready_for_preview"
            assert data["warning"] is not None
            assert data["preview_type"] == "early"
        finally:
            app.dependency_overrides.pop(deps.get_conversation_flow, None)

    @pytest.mark.asyncio
    async def test_force_preview_false_returns_no_warning_for_normal_flow(
        self, app: Any, client: AsyncClient
    ) -> None:
        mock_flow = self._make_mock_flow(
            [
                {
                    "status": "pending_confirmation",
                    "message": "I recommend HR Management.",
                    "bundle_key": "hr_management",
                    "extracted": ExtractionResult(session_id="placeholder"),
                    "suggested": None,
                    "slots": {},
                }
            ]
        )
        app.dependency_overrides[deps.get_conversation_flow] = lambda: mock_flow

        try:
            start_resp = await client.post(
                "/sessions",
                json={"message": "I manage HR"},
            )
            sid = start_resp.json()["session_id"]

            reply_resp = await client.post(
                f"/sessions/{sid}/reply",
                json={"message": "tell me more", "force_preview": False},
            )
            assert reply_resp.status_code == 200
            data = reply_resp.json()
            assert data["warning"] is None
            assert data["preview_type"] is None
        finally:
            app.dependency_overrides.pop(deps.get_conversation_flow, None)
