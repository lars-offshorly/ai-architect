"""Integration test: /preview -> /app manifest-only roundtrip.

Verifies that the manifest produced by /preview is a valid and complete
input to /app, with no other fields required.
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


_HR_HISTORY = [
    ("user", "We manage a team of 80 employees across HR and operations."),
    ("assistant", "Got it. I'll set up an HR management workspace for you."),
]

_TICKETING_HISTORY = [
    ("user", "We run a BPO contact center handling customer support tickets."),
    ("assistant", "Understood. Setting up a ticketing bundle for your team."),
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_preview_response_contains_manifest(client: AsyncClient) -> None:
    sid = _seed("hr_management", _HR_HISTORY)
    resp = await client.post(f"/sessions/{sid}/preview")
    assert resp.status_code == 200
    data = resp.json()
    assert "manifest" in data
    assert isinstance(data["manifest"], dict)
    assert data["manifest"].get("schema_version") == "2.0"


@pytest.mark.asyncio
async def test_preview_manifest_accepted_by_app(client: AsyncClient) -> None:
    sid = _seed("hr_management", _HR_HISTORY)

    preview = (await client.post(f"/sessions/{sid}/preview")).json()
    assert preview.get("manifest"), "preview must contain a manifest to proceed"

    app_resp = await client.post(
        f"/sessions/{sid}/app",
        json={"manifest": preview["manifest"]},
    )
    assert app_resp.status_code == 200
    data = app_resp.json()
    assert data["bundle_key"] == "hr_management"
    assert data["schema_version"] == "2.0"
    assert data["manifest"] == preview["manifest"]


@pytest.mark.asyncio
async def test_app_rejects_empty_manifest(client: AsyncClient) -> None:
    sid = _seed("ticketing", _TICKETING_HISTORY)
    resp = await client.post(f"/sessions/{sid}/app", json={"manifest": {}})
    assert resp.status_code == 422
