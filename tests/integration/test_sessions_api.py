"""Integration tests for the /sessions conversation lifecycle endpoints.

Verifies the full request/response cycle for:
  - POST /sessions (create + first turn)
  - POST /sessions/{id}/reply (subsequent turns, proves cross-turn persistence)
  - POST /sessions/{id}/confirm (bundle confirmation/rejection)
  - 404 for unknown sessions
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from api import deps
from domain.models.extraction_result import ExtractionResult


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


def _make_mock_flow(*results: dict) -> Any:
    """Return a mock ConversationFlow that yields results in order."""
    call_index = 0

    async def _process_turn(*_args: Any, **_kwargs: Any) -> dict:
        nonlocal call_index
        result = results[min(call_index, len(results) - 1)]
        call_index += 1
        return result

    mock = MagicMock()
    mock.process_turn = _process_turn
    return mock


_PLACEHOLDER_EXTRACTED = ExtractionResult(session_id="placeholder")


class TestSessionLifecycle:
    @pytest.mark.asyncio
    async def test_start_session_returns_201_with_session_id(
        self, app: Any, client: AsyncClient
    ) -> None:
        mock_flow = _make_mock_flow(
            {
                "status": "awaiting_input",
                "question": "What industry are you in?",
                "extracted": _PLACEHOLDER_EXTRACTED,
                "slots": {},
            }
        )
        app.dependency_overrides[deps.get_conversation_flow] = lambda: mock_flow
        try:
            resp = await client.post("/sessions", json={"message": "I need HR help"})
            assert resp.status_code == 201
            data = resp.json()
            assert "session_id" in data
            assert data["status"] == "awaiting_input"
            assert data["question"] == "What industry are you in?"
        finally:
            app.dependency_overrides.pop(deps.get_conversation_flow, None)

    @pytest.mark.asyncio
    async def test_reply_finds_session_created_by_start(
        self, app: Any, client: AsyncClient
    ) -> None:
        """Session persists between POST /sessions and POST /sessions/{id}/reply."""
        mock_flow = _make_mock_flow(
            {
                "status": "awaiting_input",
                "question": "What industry are you in?",
                "extracted": _PLACEHOLDER_EXTRACTED,
                "slots": {},
            },
            {
                "status": "pending_confirmation",
                "message": "I recommend HR Management. Ready to proceed?",
                "extracted": _PLACEHOLDER_EXTRACTED,
                "slots": {},
            },
        )
        app.dependency_overrides[deps.get_conversation_flow] = lambda: mock_flow
        try:
            start_resp = await client.post(
                "/sessions", json={"message": "I need HR help"}
            )
            assert start_resp.status_code == 201
            session_id = start_resp.json()["session_id"]

            reply_resp = await client.post(
                f"/sessions/{session_id}/reply",
                json={"message": "We are in manufacturing"},
            )
            assert reply_resp.status_code == 200
            data = reply_resp.json()
            assert data["status"] == "pending_confirmation"
            assert data["session_id"] == session_id
        finally:
            app.dependency_overrides.pop(deps.get_conversation_flow, None)

    @pytest.mark.asyncio
    async def test_reply_to_unknown_session_returns_404(
        self, app: Any, client: AsyncClient
    ) -> None:
        # Override flow to prevent real ConversationFlow construction (needs OpenAI key).
        # The route hits session_repo.get() before calling the flow, so 404 fires first.
        app.dependency_overrides[deps.get_conversation_flow] = lambda: MagicMock()
        try:
            resp = await client.post(
                "/sessions/nonexistent-session-id/reply",
                json={"message": "hello"},
            )
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.pop(deps.get_conversation_flow, None)

    @pytest.mark.asyncio
    async def test_confirm_bundle_returns_ready_for_preview(
        self, app: Any, client: AsyncClient
    ) -> None:
        mock_flow = _make_mock_flow(
            {
                "status": "pending_confirmation",
                "message": "I recommend HR Management. Confirm?",
                "extracted": _PLACEHOLDER_EXTRACTED,
                "slots": {},
                "bundle_key": "hr_management",
            }
        )
        app.dependency_overrides[deps.get_conversation_flow] = lambda: mock_flow
        try:
            start_resp = await client.post(
                "/sessions", json={"message": "I need HR features"}
            )
            assert start_resp.status_code == 201
            session_id = start_resp.json()["session_id"]

            confirm_resp = await client.post(
                f"/sessions/{session_id}/confirm", json={"confirmed": True}
            )
            assert confirm_resp.status_code == 200
            data = confirm_resp.json()
            assert data["status"] == "ready_for_preview"
            assert data["session_id"] == session_id
        finally:
            app.dependency_overrides.pop(deps.get_conversation_flow, None)

    @pytest.mark.asyncio
    async def test_reject_bundle_keeps_session_in_progress(
        self, app: Any, client: AsyncClient
    ) -> None:
        mock_flow = _make_mock_flow(
            {
                "status": "pending_confirmation",
                "message": "I recommend HR Management. Confirm?",
                "extracted": _PLACEHOLDER_EXTRACTED,
                "slots": {},
            }
        )
        app.dependency_overrides[deps.get_conversation_flow] = lambda: mock_flow
        try:
            start_resp = await client.post(
                "/sessions", json={"message": "I need something"}
            )
            session_id = start_resp.json()["session_id"]

            confirm_resp = await client.post(
                f"/sessions/{session_id}/confirm", json={"confirmed": False}
            )
            assert confirm_resp.status_code == 200
            data = confirm_resp.json()
            assert data["status"] == "in_progress"
        finally:
            app.dependency_overrides.pop(deps.get_conversation_flow, None)

    @pytest.mark.asyncio
    async def test_confirm_unknown_session_returns_404(
        self, app: Any, client: AsyncClient
    ) -> None:
        resp = await client.post(
            "/sessions/nonexistent-session-id/confirm", json={"confirmed": True}
        )
        assert resp.status_code == 404
