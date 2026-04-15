"""End-to-end integration: Dev A → Preview Generator.

Two test layers:

Layer 1 — Direct handoff
  Simulates the exact state Dev A produces after a confirmed conversation:
    • Session with confirmed=True and selected_bundle_key set
    • Conversation messages in ConversationRepository
  Then calls POST /sessions/{id}/preview and asserts the response.
  No mocking required — tests the contract boundary directly.

Layer 2 — Full HTTP flow with mocked ConversationFlow
  Drives POST /sessions → /reply → /confirm → /preview over the actual
  FastAPI app. Validates that selected_bundle_key is written to the session
  during the conversation turn (the bug that would have caused 400 on /preview).

Bundle key mapping under test (catalog → registry):
  hr_management → hr_hub       (Tier 1, key translation)
  project_mgmt  → project_mgmt (Tier 1)
  ticketing     → ticketing    (Tier 1)
"""

# pylint: disable=missing-class-docstring,missing-function-docstring

from __future__ import annotations

import importlib
import os
import uuid
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from api.deps import (
    get_conversation_repository,
    get_session_repository,
)
from domain.models.conversation import ConversationMessage
from domain.models.extraction_result import ExtractionResult
from domain.models.session import Session

# ---------------------------------------------------------------------------
# App fixture — shared across tests (same lru_cache state as production)
# ---------------------------------------------------------------------------


@pytest.fixture(name="app", scope="module")
def fixture_app():
    import sys
    from pathlib import Path

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unique_id() -> str:
    return str(uuid.uuid4())


def _seed_confirmed_session(
    session_id: str,
    bundle_key: str,
    history: list[tuple[str, str]],
) -> None:
    """Pre-populate repos the same way Dev A's conversation flow would."""
    session_repo = get_session_repository()
    conv_repo = get_conversation_repository()

    session = Session(
        session_id=session_id,
        confirmed=True,
        selected_bundle_key=bundle_key,
    )
    session_repo.save(session)

    for role, content in history:
        conv_repo.append_message(
            session_id,
            ConversationMessage(role=role, content=content),  # type: ignore[arg-type]
        )


# Realistic conversation histories (mirror what the session.py router would record)
_HR_HUB_HISTORY: list[tuple[str, str]] = [
    ("assistant", "Tell me about your team."),
    (
        "user",
        "We run HR at Vertex Solutions, 200 employees."
        " Onboarding and leave management are our main challenges.",
    ),
    (
        "assistant",
        "Sounds like HR Hub — tickets, queues, KPIs. How many on your HR team?",
    ),
    (
        "user",
        "12 people. Maria Santos leads onboarding, Carlos Mendez handles compliance.",
    ),
    ("assistant", "HR Hub confirmed. Ready to generate your preview?"),
    ("user", "Yes."),
]

_PROJECT_OPS_HISTORY: list[tuple[str, str]] = [
    ("assistant", "What does your team work on?"),
    (
        "user",
        "30-person engineering team at NovaBuild."
        " We run two-week sprints and track milestones.",
    ),
    (
        "assistant",
        "Project Operations — tasks, milestones, KPI dashboard. Does that fit?",
    ),
    ("user", "Yes, we also need capacity utilisation metrics."),
]

_FIELD_SERVICE_HISTORY: list[tuple[str, str]] = [
    ("assistant", "What kind of work does your team handle?"),
    (
        "user",
        "IT help desk at ClearPath."
        " Bug reports, access requests, SLA-bound support tickets.",
    ),
    ("assistant", "Field Service / Ticketing with SLA tracking. Shall I set that up?"),
    ("user", "Confirmed."),
]


# ===========================================================================
# Layer 1 — Direct handoff tests (pre-seeded session state)
# ===========================================================================


class TestDirectHandoff:
    """Dev A has finished the conversation and confirmed the bundle.
    These tests verify our preview endpoint accepts and processes that state.
    """

    @pytest.mark.asyncio
    async def test_hr_hub_returns_200(self, client: AsyncClient) -> None:
        sid = _unique_id()
        _seed_confirmed_session(sid, "hr_management", _HR_HUB_HISTORY)

        resp = await client.post(f"/sessions/{sid}/preview")
        assert resp.status_code == 200, resp.text

    @pytest.mark.asyncio
    async def test_hr_hub_response_schema(self, client: AsyncClient) -> None:
        sid = _unique_id()
        _seed_confirmed_session(sid, "hr_management", _HR_HUB_HISTORY)

        data = (await client.post(f"/sessions/{sid}/preview")).json()

        assert data["schema_version"] == "1.0"
        assert data["session_id"] == sid
        assert data["bundle_key"] == "hr_management"
        assert data["display_name"] == "HR Management"
        assert isinstance(data["modules"], list)
        assert isinstance(data["generation_json"], dict)
        assert isinstance(data["dummy_data_json"], dict)

    @pytest.mark.asyncio
    async def test_hr_hub_generation_json_has_flags(self, client: AsyncClient) -> None:
        sid = _unique_id()
        _seed_confirmed_session(sid, "hr_management", _HR_HUB_HISTORY)

        data = (await client.post(f"/sessions/{sid}/preview")).json()
        flags = data["generation_json"]["feature_flags"]
        assert len(flags) > 0
        flag_map = {f["name"]: f["isEnabled"] for f in flags}
        assert flag_map["hrhub-module"] is True

    @pytest.mark.asyncio
    async def test_hr_hub_dummy_data_store_names(self, client: AsyncClient) -> None:
        sid = _unique_id()
        _seed_confirmed_session(sid, "hr_management", _HR_HUB_HISTORY)

        data = (await client.post(f"/sessions/{sid}/preview")).json()
        stores = data["dummy_data_json"]["stores"]
        assert "tickets" in stores
        assert "queues" in stores
        assert "kpis" in stores

    @pytest.mark.asyncio
    async def test_hr_hub_company_name_in_dummy_data(self, client: AsyncClient) -> None:
        sid = _unique_id()
        _seed_confirmed_session(sid, "hr_management", _HR_HUB_HISTORY)

        data = (await client.post(f"/sessions/{sid}/preview")).json()
        # "Vertex Solutions" is mentioned in the conversation
        assert data["dummy_data_json"]["company_name"] == "Vertex Solutions"

    @pytest.mark.asyncio
    async def test_project_ops_returns_200(self, client: AsyncClient) -> None:
        sid = _unique_id()
        _seed_confirmed_session(sid, "project_mgmt", _PROJECT_OPS_HISTORY)

        resp = await client.post(f"/sessions/{sid}/preview")
        assert resp.status_code == 200, resp.text

    @pytest.mark.asyncio
    async def test_project_ops_store_names(self, client: AsyncClient) -> None:
        sid = _unique_id()
        _seed_confirmed_session(sid, "project_mgmt", _PROJECT_OPS_HISTORY)

        data = (await client.post(f"/sessions/{sid}/preview")).json()
        stores = data["dummy_data_json"]["stores"]
        assert "tasks" in stores
        assert "milestones" in stores

    @pytest.mark.asyncio
    async def test_field_service_returns_200(self, client: AsyncClient) -> None:
        sid = _unique_id()
        _seed_confirmed_session(sid, "ticketing", _FIELD_SERVICE_HISTORY)

        resp = await client.post(f"/sessions/{sid}/preview")
        assert resp.status_code == 200, resp.text

    @pytest.mark.asyncio
    async def test_field_service_store_names(self, client: AsyncClient) -> None:
        sid = _unique_id()
        _seed_confirmed_session(sid, "ticketing", _FIELD_SERVICE_HISTORY)

        data = (await client.post(f"/sessions/{sid}/preview")).json()
        stores = data["dummy_data_json"]["stores"]
        assert "tickets" in stores
        assert "queues" in stores

    @pytest.mark.asyncio
    async def test_unconfirmed_session_returns_400(self, client: AsyncClient) -> None:
        sid = _unique_id()
        session_repo = get_session_repository()
        session_repo.save(Session(session_id=sid, confirmed=False))

        resp = await client.post(f"/sessions/{sid}/preview")
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_confirmed_but_no_bundle_key_returns_400(
        self, client: AsyncClient
    ) -> None:
        sid = _unique_id()
        session_repo = get_session_repository()
        session_repo.save(
            Session(session_id=sid, confirmed=True, selected_bundle_key=None)
        )

        resp = await client.post(f"/sessions/{sid}/preview")
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_missing_session_returns_404(self, client: AsyncClient) -> None:
        resp = await client.post(f"/sessions/{_unique_id()}/preview")
        assert resp.status_code == 404


# ===========================================================================
# Layer 2 — Full HTTP flow with mocked ConversationFlow
# ===========================================================================


class TestFullHttpFlow:
    """Drives the complete API sequence that a frontend client would use.

    Uses FastAPI dependency_overrides to inject a mock ConversationFlow so
    that InterpreterService (which requires an OpenAI API key) is never
    constructed. The key assertions verify selected_bundle_key is written to
    the session during turns — without this, /preview always returns 400.
    """

    def _make_mock_flow(self, sequence: list[dict]) -> object:
        """Return a mock ConversationFlow whose process_turn yields from sequence."""
        from unittest.mock import MagicMock

        call_count = 0

        async def _process_turn(*_args: Any, **_kwargs: Any) -> object:
            nonlocal call_count
            result = sequence[min(call_count, len(sequence) - 1)]
            call_count += 1
            return await _identity(result)

        async def _identity(value):  # noqa: ANN001, ANN202
            return value

        mock = MagicMock()
        mock.process_turn = _process_turn
        return mock

    @pytest.mark.asyncio
    async def test_selected_bundle_key_is_saved_after_pending_confirmation(
        self, app: Any, client: AsyncClient
    ) -> None:
        """When ConversationFlow returns pending_confirmation, the session
        should have selected_bundle_key set — so /confirm → /preview works.
        """
        from api import deps

        mock_flow = self._make_mock_flow(
            [
                {
                    "status": "pending_confirmation",
                    "message": "I recommend HR Management. Does this look right?",
                    "bundle_key": "hr_management",
                    "extracted": ExtractionResult(session_id="placeholder"),
                    "slots": {"team_size": "12"},
                }
            ]
        )
        app.dependency_overrides[deps.get_conversation_flow] = lambda: mock_flow

        try:
            # Step 1: Start session → pending_confirmation
            start_resp = await client.post(
                "/sessions",
                json={"message": "I manage HR at a 200-person company"},
            )
            assert start_resp.status_code == 201
            start_data = start_resp.json()
            assert start_data["status"] == "pending_confirmation"
            assert start_data["bundle_key"] == "hr_management"
            sid = start_data["session_id"]

            # Step 2: selected_bundle_key must be written to the session
            session = get_session_repository().get(sid)
            assert session.selected_bundle_key == "hr_management", (
                "selected_bundle_key must be set when process_turn returns bundle_key "
                "— otherwise /preview will always return 400"
            )

            # Step 3: Confirm
            confirm_resp = await client.post(
                f"/sessions/{sid}/confirm",
                json={"confirmed": True},
            )
            assert confirm_resp.status_code == 200
            assert confirm_resp.json()["status"] == "ready_for_preview"

            # Step 4: Preview — must succeed (200, not 400)
            preview_resp = await client.post(f"/sessions/{sid}/preview")
            assert preview_resp.status_code == 200, preview_resp.text

            data = preview_resp.json()
            assert data["bundle_key"] == "hr_management"
            assert data["display_name"] == "HR Management"
            enabled_flags = {
                f["name"]
                for f in data["generation_json"]["feature_flags"]
                if f["isEnabled"]
            }
            assert "hrhub-module" in enabled_flags
        finally:
            app.dependency_overrides.pop(deps.get_conversation_flow, None)

    @pytest.mark.asyncio
    async def test_full_conversation_reply_then_preview(
        self, app: Any, client: AsyncClient
    ) -> None:
        """Start → reply (pending_confirmation) → confirm → preview."""
        from api import deps

        mock_flow = self._make_mock_flow(
            [
                {
                    "status": "awaiting_input",
                    "question": "How many people are on your HR team?",
                    "bundle_key": None,
                    "extracted": ExtractionResult(session_id="placeholder"),
                    "slots": {},
                },
                {
                    "status": "pending_confirmation",
                    "message": "I recommend HR Management. Does this look right?",
                    "bundle_key": "hr_management",
                    "extracted": ExtractionResult(session_id="placeholder"),
                    "slots": {"team_size": "12"},
                },
            ]
        )
        app.dependency_overrides[deps.get_conversation_flow] = lambda: mock_flow

        try:
            # Step 1: Start → awaiting_input
            start_resp = await client.post(
                "/sessions",
                json={"message": "We need a workspace for our HR team"},
            )
            assert start_resp.status_code == 201
            assert start_resp.json()["status"] == "awaiting_input"
            sid = start_resp.json()["session_id"]
            assert get_session_repository().get(sid).selected_bundle_key is None

            # Step 2: Reply → pending_confirmation with bundle_key
            reply_resp = await client.post(
                f"/sessions/{sid}/reply",
                json={"message": "12 people"},
            )
            assert reply_resp.status_code == 200
            assert reply_resp.json()["status"] == "pending_confirmation"
            assert reply_resp.json()["bundle_key"] == "hr_management"
            assert (
                get_session_repository().get(sid).selected_bundle_key == "hr_management"
            )

            # Step 3: Confirm
            confirm_resp = await client.post(
                f"/sessions/{sid}/confirm",
                json={"confirmed": True},
            )
            assert confirm_resp.status_code == 200

            # Step 4: Preview
            preview_resp = await client.post(f"/sessions/{sid}/preview")
            assert preview_resp.status_code == 200
            assert preview_resp.json()["bundle_key"] == "hr_management"
        finally:
            app.dependency_overrides.pop(deps.get_conversation_flow, None)

    @pytest.mark.asyncio
    async def test_preview_without_confirm_returns_400(
        self, app: Any, client: AsyncClient
    ) -> None:
        """selected_bundle_key set but confirmed=False → /preview must reject."""
        from api import deps

        mock_flow = self._make_mock_flow(
            [
                {
                    "status": "pending_confirmation",
                    "message": "I recommend Project Management.",
                    "bundle_key": "project_mgmt",
                    "extracted": ExtractionResult(session_id="placeholder"),
                    "slots": {},
                }
            ]
        )
        app.dependency_overrides[deps.get_conversation_flow] = lambda: mock_flow

        try:
            start_resp = await client.post(
                "/sessions",
                json={"message": "We manage engineering sprints"},
            )
            sid = start_resp.json()["session_id"]

            session = get_session_repository().get(sid)
            assert session.selected_bundle_key == "project_mgmt"
            assert session.confirmed is False

            preview_resp = await client.post(f"/sessions/{sid}/preview")
            assert preview_resp.status_code == 400
        finally:
            app.dependency_overrides.pop(deps.get_conversation_flow, None)
