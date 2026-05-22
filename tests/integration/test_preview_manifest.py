"""Integration tests: /preview returns a populated manifest for a canonical bundle.

Focuses on manifest content quality — that the pipeline actually populated
all required sections, not just that the manifest key is present.
"""

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
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _uid() -> str:
    return str(uuid.uuid4())


def _seed(bundle_key: str, history: list[tuple[str, str]]) -> str:
    sid = _uid()
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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_preview_manifest_present_with_schema_version(client: AsyncClient) -> None:
    sid = _seed("hr_management", _HR_HISTORY)
    data = (await client.post(f"/sessions/{sid}/preview")).json()
    assert "manifest" in data
    assert data["manifest"]["schema_version"] == "2.0"


@pytest.mark.asyncio
async def test_preview_manifest_has_all_sections(client: AsyncClient) -> None:
    sid = _seed("hr_management", _HR_HISTORY)
    manifest = (await client.post(f"/sessions/{sid}/preview")).json()["manifest"]
    for section in ("tenant", "tickets", "projects", "dashboard", "kpi", "hr_hub"):
        assert section in manifest, f"missing section: {section}"


@pytest.mark.asyncio
async def test_preview_manifest_session_id_matches(client: AsyncClient) -> None:
    sid = _seed("hr_management", _HR_HISTORY)
    manifest = (await client.post(f"/sessions/{sid}/preview")).json()["manifest"]
    assert manifest["session_id"] == sid


@pytest.mark.asyncio
async def test_preview_manifest_kpis_populated(client: AsyncClient) -> None:
    sid = _seed("hr_management", _HR_HISTORY)
    manifest = (await client.post(f"/sessions/{sid}/preview")).json()["manifest"]
    kpis = manifest["kpi"]["kpis"]
    assert isinstance(kpis, list)
    assert len(kpis) > 0
