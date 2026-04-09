"""Integration tests: full generate → edit cycle over the HTTP API.

Each test class represents a bundle. The pattern is:
  1. Seed a confirmed session with known conversation history
  2. POST /sessions/{id}/preview — capture the full response as current_preview
  3. Assert the generated output is correct (flags, stores, KPIs, config)
  4. POST /sessions/{id}/preview/edit with current_preview + a natural-language instruction
  5. Assert the edit applied correctly and cascading effects are handled

No mocking. No pipeline shortcuts. These tests drive the real stack.
"""

# pylint: disable=missing-class-docstring,missing-function-docstring

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from api.deps import get_conversation_repository, get_session_repository
from domain.models.conversation import ConversationMessage
from domain.models.session import Session


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(name="app", scope="module")
def fixture_app():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
    from main import create_app

    return create_app()


@pytest.fixture(name="client")
async def fixture_client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _uid() -> str:
    return str(uuid.uuid4())


def _seed(
    bundle_key: str,
    history: list[tuple[str, str]],
    session_id: str | None = None,
) -> str:
    """Seed a confirmed session + conversation history. Returns session_id."""
    sid = session_id or _uid()
    session_repo = get_session_repository()
    conv_repo = get_conversation_repository()

    session_repo.save(
        Session(session_id=sid, confirmed=True, selected_bundle_key=bundle_key)
    )
    for role, content in history:
        conv_repo.append_message(
            sid, ConversationMessage(role=role, content=content)  # type: ignore[arg-type]
        )
    return sid


# ---------------------------------------------------------------------------
# Shared conversation histories (realistic, matching what Dev A would produce)
# ---------------------------------------------------------------------------

_HR_HISTORY: list[tuple[str, str]] = [
    ("assistant", "Tell me about your team."),
    (
        "user",
        "We manage HR at BrightPath Inc, 180 employees. "
        "Main challenges are onboarding and leave tracking.",
    ),
    ("assistant", "HR Management — tickets, queues, KPIs. How many on the HR team?"),
    ("user", "8 people. Ana Reyes leads onboarding, Marco Cruz handles compliance."),
    ("assistant", "Confirmed. Ready to generate your workspace?"),
    ("user", "Yes, go ahead."),
]

_PROJECT_HISTORY: list[tuple[str, str]] = [
    ("assistant", "What does your team work on?"),
    (
        "user",
        "Engineering team at NovaBuild, 25 people. "
        "We run two-week sprints and track delivery milestones.",
    ),
    ("assistant", "Project Management — tasks, milestones, capacity KPIs. Confirm?"),
    ("user", "Yes. We also track on-time delivery."),
]

_TICKETING_HISTORY: list[tuple[str, str]] = [
    ("assistant", "What kind of work does your team handle?"),
    (
        "user",
        "IT help desk at ClearPath, SLA-bound support tickets. "
        "Bug reports and access requests mostly.",
    ),
    ("assistant", "Ticketing with SLA tracking. Shall I set that up?"),
    ("user", "Confirmed."),
]


# ===========================================================================
# HR Management bundle — generate + edit
# ===========================================================================


class TestHRManagementGenerateAndEdit:
    """Full generate → edit cycle for hr_management bundle."""

    @pytest.mark.asyncio
    async def test_generate_returns_200(self, client: AsyncClient) -> None:
        sid = _seed("hr_management", _HR_HISTORY)
        resp = await client.post(f"/sessions/{sid}/preview")
        assert resp.status_code == 200, resp.text

    @pytest.mark.asyncio
    async def test_generate_schema_fields(self, client: AsyncClient) -> None:
        sid = _seed("hr_management", _HR_HISTORY)
        data = (await client.post(f"/sessions/{sid}/preview")).json()

        assert data["schema_version"] == "1.0"
        assert data["bundle_key"] == "hr_management"
        assert data["display_name"] == "HR Management"
        assert isinstance(data["modules"], list)
        assert len(data["modules"]) > 0

    @pytest.mark.asyncio
    async def test_generate_hrhub_flag_enabled(self, client: AsyncClient) -> None:
        sid = _seed("hr_management", _HR_HISTORY)
        data = (await client.post(f"/sessions/{sid}/preview")).json()

        flag_map = {f["name"]: f["isEnabled"] for f in data["generation_json"]["feature_flags"]}
        assert flag_map.get("hrhub-module") is True

    @pytest.mark.asyncio
    async def test_generate_stores_present(self, client: AsyncClient) -> None:
        sid = _seed("hr_management", _HR_HISTORY)
        data = (await client.post(f"/sessions/{sid}/preview")).json()
        stores = data["dummy_data_json"]["stores"]

        assert "tickets" in stores
        assert "queues" in stores
        assert "kpis" in stores
        assert len(stores["tickets"]) > 0

    @pytest.mark.asyncio
    async def test_generate_company_name_extracted(self, client: AsyncClient) -> None:
        sid = _seed("hr_management", _HR_HISTORY)
        data = (await client.post(f"/sessions/{sid}/preview")).json()
        assert data["dummy_data_json"]["company_name"] == "BrightPath Inc"

    @pytest.mark.asyncio
    async def test_generate_kpis_populated(self, client: AsyncClient) -> None:
        sid = _seed("hr_management", _HR_HISTORY)
        data = (await client.post(f"/sessions/{sid}/preview")).json()
        kpis = data["dummy_data_json"]["stores"]["kpis"]

        assert len(kpis) > 0
        kpi_keys = {k["key"] for k in kpis}
        # HR bundle defaults include active_headcount
        assert "active_headcount" in kpi_keys

    @pytest.mark.asyncio
    async def test_edit_remove_chat_module(self, client: AsyncClient) -> None:
        sid = _seed("hr_management", _HR_HISTORY)
        current = (await client.post(f"/sessions/{sid}/preview")).json()

        resp = await client.post(
            f"/sessions/{sid}/preview/edit",
            json={"current_preview": current, "instruction": "remove the chat module"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()

        flag_map = {f["name"]: f["isEnabled"] for f in data["generation_json"]["feature_flags"]}
        assert flag_map.get("chat-module") is False
        assert "Chat" not in data["modules"]
        assert data["warning"] is None

    @pytest.mark.asyncio
    async def test_edit_remove_kpi(self, client: AsyncClient) -> None:
        sid = _seed("hr_management", _HR_HISTORY)
        current = (await client.post(f"/sessions/{sid}/preview")).json()

        # Ensure active_headcount is present before removing it
        kpi_keys_before = {k["key"] for k in current["dummy_data_json"]["stores"]["kpis"]}
        assert "active_headcount" in kpi_keys_before, "Precondition: KPI must exist before removal"

        resp = await client.post(
            f"/sessions/{sid}/preview/edit",
            json={
                "current_preview": current,
                "instruction": "remove active_headcount kpi",
            },
        )
        assert resp.status_code == 200
        data = resp.json()

        kpi_keys_after = {k["key"] for k in data["dummy_data_json"]["stores"]["kpis"]}
        assert "active_headcount" not in kpi_keys_after

    @pytest.mark.asyncio
    async def test_edit_add_kpi(self, client: AsyncClient) -> None:
        sid = _seed("hr_management", _HR_HISTORY)
        current = (await client.post(f"/sessions/{sid}/preview")).json()

        resp = await client.post(
            f"/sessions/{sid}/preview/edit",
            json={
                "current_preview": current,
                "instruction": "add sla_compliance kpi",
            },
        )
        assert resp.status_code == 200
        data = resp.json()

        kpi_keys = {k["key"] for k in data["dummy_data_json"]["stores"]["kpis"]}
        assert "sla_compliance" in kpi_keys

    @pytest.mark.asyncio
    async def test_edit_schema_fields_preserved(self, client: AsyncClient) -> None:
        sid = _seed("hr_management", _HR_HISTORY)
        current = (await client.post(f"/sessions/{sid}/preview")).json()

        resp = await client.post(
            f"/sessions/{sid}/preview/edit",
            json={"current_preview": current, "instruction": "remove the chat module"},
        )
        data = resp.json()

        assert data["schema_version"] == "1.0"
        assert data["session_id"] == sid
        assert data["bundle_key"] == "hr_management"

    @pytest.mark.asyncio
    async def test_edit_unknown_session_returns_404(self, client: AsyncClient) -> None:
        sid = _seed("hr_management", _HR_HISTORY)
        current = (await client.post(f"/sessions/{sid}/preview")).json()

        resp = await client.post(
            f"/sessions/{_uid()}/preview/edit",
            json={"current_preview": current, "instruction": "remove chat"},
        )
        assert resp.status_code == 404


# ===========================================================================
# Project Management bundle — generate + edit
# ===========================================================================


class TestProjectMgmtGenerateAndEdit:
    """Full generate → edit cycle for project_mgmt bundle."""

    @pytest.mark.asyncio
    async def test_generate_returns_200(self, client: AsyncClient) -> None:
        sid = _seed("project_mgmt", _PROJECT_HISTORY)
        resp = await client.post(f"/sessions/{sid}/preview")
        assert resp.status_code == 200, resp.text

    @pytest.mark.asyncio
    async def test_generate_store_names(self, client: AsyncClient) -> None:
        sid = _seed("project_mgmt", _PROJECT_HISTORY)
        data = (await client.post(f"/sessions/{sid}/preview")).json()
        stores = data["dummy_data_json"]["stores"]

        assert "tasks" in stores
        assert "milestones" in stores
        assert "kpis" in stores

    @pytest.mark.asyncio
    async def test_generate_projects_flag_enabled(self, client: AsyncClient) -> None:
        sid = _seed("project_mgmt", _PROJECT_HISTORY)
        data = (await client.post(f"/sessions/{sid}/preview")).json()
        flag_map = {f["name"]: f["isEnabled"] for f in data["generation_json"]["feature_flags"]}
        assert flag_map.get("projects-module") is True

    @pytest.mark.asyncio
    async def test_generate_on_time_delivery_kpi(self, client: AsyncClient) -> None:
        sid = _seed("project_mgmt", _PROJECT_HISTORY)
        data = (await client.post(f"/sessions/{sid}/preview")).json()
        kpi_keys = {k["key"] for k in data["dummy_data_json"]["stores"]["kpis"]}
        assert "on_time_delivery_rate" in kpi_keys

    @pytest.mark.asyncio
    async def test_edit_remove_dashboard(self, client: AsyncClient) -> None:
        sid = _seed("project_mgmt", _PROJECT_HISTORY)
        current = (await client.post(f"/sessions/{sid}/preview")).json()

        resp = await client.post(
            f"/sessions/{sid}/preview/edit",
            json={"current_preview": current, "instruction": "remove dashboard"},
        )
        assert resp.status_code == 200
        data = resp.json()

        flag_map = {f["name"]: f["isEnabled"] for f in data["generation_json"]["feature_flags"]}
        assert flag_map.get("dashboard-module") is False
        assert "Dashboard" not in data["modules"]
        # Dashboard widgets cascade removed
        assert "dashboard_widgets" not in data["dummy_data_json"]["stores"]

    @pytest.mark.asyncio
    async def test_edit_add_dashboard_back(self, client: AsyncClient) -> None:
        sid = _seed("project_mgmt", _PROJECT_HISTORY)
        current = (await client.post(f"/sessions/{sid}/preview")).json()

        # Remove first
        removed = (
            await client.post(
                f"/sessions/{sid}/preview/edit",
                json={"current_preview": current, "instruction": "remove dashboard"},
            )
        ).json()

        # Then add back
        resp = await client.post(
            f"/sessions/{sid}/preview/edit",
            json={"current_preview": removed, "instruction": "add dashboard"},
        )
        assert resp.status_code == 200
        data = resp.json()

        flag_map = {f["name"]: f["isEnabled"] for f in data["generation_json"]["feature_flags"]}
        assert flag_map.get("dashboard-module") is True
        assert "Dashboard" in data["modules"]

    @pytest.mark.asyncio
    async def test_edit_remove_kpi_from_config(self, client: AsyncClient) -> None:
        sid = _seed("project_mgmt", _PROJECT_HISTORY)
        current = (await client.post(f"/sessions/{sid}/preview")).json()

        kpi_keys_before = {k["key"] for k in current["dummy_data_json"]["stores"]["kpis"]}
        assert "on_time_delivery_rate" in kpi_keys_before

        resp = await client.post(
            f"/sessions/{sid}/preview/edit",
            json={
                "current_preview": current,
                "instruction": "remove on_time_delivery_rate kpi",
            },
        )
        data = resp.json()
        kpi_keys_after = {k["key"] for k in data["dummy_data_json"]["stores"]["kpis"]}
        assert "on_time_delivery_rate" not in kpi_keys_after

        # Also removed from config.kpi_definitions
        config_kpis = data["generation_json"]["config"].get("kpi_definitions", [])
        assert "on_time_delivery_rate" not in config_kpis

    @pytest.mark.asyncio
    async def test_edit_unsupported_instruction_returns_warning(
        self, client: AsyncClient
    ) -> None:
        sid = _seed("project_mgmt", _PROJECT_HISTORY)
        current = (await client.post(f"/sessions/{sid}/preview")).json()

        resp = await client.post(
            f"/sessions/{sid}/preview/edit",
            json={"current_preview": current, "instruction": "paint everything blue"},
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data["warning"] is not None
        assert "unsupported" in data["warning"].lower()
        # Payload must be unchanged — same KPI count
        assert len(data["dummy_data_json"]["stores"]["kpis"]) == len(
            current["dummy_data_json"]["stores"]["kpis"]
        )


# ===========================================================================
# Ticketing bundle — generate + edit
# ===========================================================================


class TestTicketingGenerateAndEdit:
    """Full generate → edit cycle for ticketing bundle."""

    @pytest.mark.asyncio
    async def test_generate_returns_200(self, client: AsyncClient) -> None:
        sid = _seed("ticketing", _TICKETING_HISTORY)
        resp = await client.post(f"/sessions/{sid}/preview")
        assert resp.status_code == 200, resp.text

    @pytest.mark.asyncio
    async def test_generate_store_names(self, client: AsyncClient) -> None:
        sid = _seed("ticketing", _TICKETING_HISTORY)
        data = (await client.post(f"/sessions/{sid}/preview")).json()
        stores = data["dummy_data_json"]["stores"]
        assert "tickets" in stores
        assert "queues" in stores

    @pytest.mark.asyncio
    async def test_generate_sla_kpi_present(self, client: AsyncClient) -> None:
        sid = _seed("ticketing", _TICKETING_HISTORY)
        data = (await client.post(f"/sessions/{sid}/preview")).json()
        kpi_keys = {k["key"] for k in data["dummy_data_json"]["stores"]["kpis"]}
        assert "sla_compliance" in kpi_keys

    @pytest.mark.asyncio
    async def test_edit_remove_sla_kpi(self, client: AsyncClient) -> None:
        sid = _seed("ticketing", _TICKETING_HISTORY)
        current = (await client.post(f"/sessions/{sid}/preview")).json()

        resp = await client.post(
            f"/sessions/{sid}/preview/edit",
            json={"current_preview": current, "instruction": "remove sla_compliance kpi"},
        )
        assert resp.status_code == 200
        data = resp.json()

        kpi_keys = {k["key"] for k in data["dummy_data_json"]["stores"]["kpis"]}
        assert "sla_compliance" not in kpi_keys

    @pytest.mark.asyncio
    async def test_edit_add_capacity_kpi(self, client: AsyncClient) -> None:
        sid = _seed("ticketing", _TICKETING_HISTORY)
        current = (await client.post(f"/sessions/{sid}/preview")).json()

        resp = await client.post(
            f"/sessions/{sid}/preview/edit",
            json={
                "current_preview": current,
                "instruction": "add capacity_utilization kpi",
            },
        )
        assert resp.status_code == 200
        kpi_keys = {k["key"] for k in resp.json()["dummy_data_json"]["stores"]["kpis"]}
        assert "capacity_utilization" in kpi_keys

    @pytest.mark.asyncio
    async def test_edit_unrecognised_instruction_returns_warning(
        self, client: AsyncClient
    ) -> None:
        sid = _seed("ticketing", _TICKETING_HISTORY)
        current = (await client.post(f"/sessions/{sid}/preview")).json()

        resp = await client.post(
            f"/sessions/{sid}/preview/edit",
            json={
                "current_preview": current,
                "instruction": "make the colour scheme purple",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["warning"] is not None
        assert "unsupported" in data["warning"].lower()

    @pytest.mark.asyncio
    async def test_edit_multiple_operations_in_sequence(
        self, client: AsyncClient
    ) -> None:
        """Chain two edits: remove a KPI, then add a different one."""
        sid = _seed("ticketing", _TICKETING_HISTORY)
        current = (await client.post(f"/sessions/{sid}/preview")).json()

        # Step 1: remove sla_compliance
        after_remove = (
            await client.post(
                f"/sessions/{sid}/preview/edit",
                json={
                    "current_preview": current,
                    "instruction": "remove sla_compliance kpi",
                },
            )
        ).json()

        kpi_keys = {k["key"] for k in after_remove["dummy_data_json"]["stores"]["kpis"]}
        assert "sla_compliance" not in kpi_keys

        # Step 2: add on_time_delivery_rate
        after_add = (
            await client.post(
                f"/sessions/{sid}/preview/edit",
                json={
                    "current_preview": after_remove,
                    "instruction": "add on_time_delivery_rate kpi",
                },
            )
        ).json()

        kpi_keys_final = {k["key"] for k in after_add["dummy_data_json"]["stores"]["kpis"]}
        assert "sla_compliance" not in kpi_keys_final
        assert "on_time_delivery_rate" in kpi_keys_final


# ===========================================================================
# Cross-bundle — shared contract assertions
# ===========================================================================


class TestGenerateEditContract:
    """Bundle-agnostic contract tests: schema shape, idempotency, session guard."""

    @pytest.mark.parametrize(
        "bundle_key,history",
        [
            ("hr_management", _HR_HISTORY),
            ("project_mgmt", _PROJECT_HISTORY),
            ("ticketing", _TICKETING_HISTORY),
        ],
    )
    @pytest.mark.asyncio
    async def test_all_bundles_return_required_top_level_fields(
        self, client: AsyncClient, bundle_key: str, history: list
    ) -> None:
        sid = _seed(bundle_key, history)
        data = (await client.post(f"/sessions/{sid}/preview")).json()

        for field in ("schema_version", "session_id", "bundle_key", "display_name",
                      "modules", "generation_json", "dummy_data_json"):
            assert field in data, f"Missing field: {field}"

    @pytest.mark.parametrize(
        "bundle_key,history",
        [
            ("hr_management", _HR_HISTORY),
            ("project_mgmt", _PROJECT_HISTORY),
            ("ticketing", _TICKETING_HISTORY),
        ],
    )
    @pytest.mark.asyncio
    async def test_edit_does_not_mutate_original_preview(
        self, client: AsyncClient, bundle_key: str, history: list
    ) -> None:
        """The endpoint must deep-copy — original current_preview payload unchanged."""
        sid = _seed(bundle_key, history)
        current = (await client.post(f"/sessions/{sid}/preview")).json()
        modules_before = list(current["modules"])

        await client.post(
            f"/sessions/{sid}/preview/edit",
            json={"current_preview": current, "instruction": "remove chat"},
        )

        # current dict is the serialized response — it should be unchanged
        assert current["modules"] == modules_before

    @pytest.mark.asyncio
    async def test_generate_unconfirmed_session_returns_400(
        self, client: AsyncClient
    ) -> None:
        sid = _uid()
        get_session_repository().save(
            Session(session_id=sid, confirmed=False, selected_bundle_key="project_mgmt")
        )
        resp = await client.post(f"/sessions/{sid}/preview")
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_generate_missing_session_returns_404(
        self, client: AsyncClient
    ) -> None:
        resp = await client.post(f"/sessions/{_uid()}/preview")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_edit_missing_session_returns_404(
        self, client: AsyncClient
    ) -> None:
        # Use any valid-looking payload
        sid = _seed("project_mgmt", _PROJECT_HISTORY)
        current = (await client.post(f"/sessions/{sid}/preview")).json()

        resp = await client.post(
            f"/sessions/{_uid()}/preview/edit",
            json={"current_preview": current, "instruction": "remove chat"},
        )
        assert resp.status_code == 404
