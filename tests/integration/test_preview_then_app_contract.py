"""Integration test: confirmed preview -> finalize app preserves payload shape."""

from __future__ import annotations

import importlib
import os
import sys
import uuid
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from api.deps import get_conversation_repository, get_session_repository
from domain.models.conversation import ConversationMessage
from domain.models.session import Session


@pytest.fixture(name="app", scope="module")
def fixture_app():
    sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
    os.environ["DEBUG"] = "True"
    os.environ["DISABLE_LLM_CALLS"] = "True"
    config_module = importlib.import_module("core.config")
    config_module.get_settings.cache_clear()
    main_module = importlib.import_module("main")
    return main_module.create_app()


@pytest.fixture(name="client")
async def fixture_client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def _unique_id() -> str:
    return str(uuid.uuid4())


def _seed_confirmed_session(session_id: str, bundle_key: str) -> None:
    session_repo = get_session_repository()
    conv_repo = get_conversation_repository()

    session_repo.save(
        Session(
            session_id=session_id,
            confirmed=True,
            selected_bundle_key=bundle_key,
        )
    )

    conv_repo.append_message(
        session_id,
        ConversationMessage(role="user", content="Generate a confirmed preview."),  # type: ignore[arg-type]
    )


@pytest.mark.asyncio
async def test_preview_then_app_preserves_dashboard_widgets(client: AsyncClient) -> None:
    sid = _unique_id()
    _seed_confirmed_session(sid, "hr_management")

    preview = (await client.post(f"/sessions/{sid}/preview")).json()
    assert preview["bundle_key"] == "hr_management"
    assert preview["preview_type"] == "confirmed"

    widgets = preview["dummy_data_json"]["stores"].get("dashboard_widgets")
    assert isinstance(widgets, list)
    assert len(widgets) > 0

    app_payload = (
        await client.post(
            f"/sessions/{sid}/app",
            json={
                "dummy_data_json": preview["dummy_data_json"],
                "generation_json": preview["generation_json"],
            },
        )
    ).json()

    assert app_payload["bundle_key"] == "hr_management"
    assert app_payload["preview_type"] == "confirmed"

    app_stores = app_payload["dummy_data_json"]["stores"]
    app_widgets = app_stores.get("dashboard_widgets")
    assert isinstance(app_widgets, list)
    assert len(app_widgets) == len(widgets)

    gen_out = app_stores.get("dashboard_generation_output")
    assert isinstance(gen_out, dict)
    assert gen_out.get("widgets", {}).get("total") == len(app_widgets)
    assert gen_out.get("dashboard", {}).get("external_id")

@pytest.mark.asyncio
async def test_v1_roundtrip_ticketing_bundle(
    client: AsyncClient,
    v1_fixture: dict,
) -> None:
    sid = _unique_id()
    _seed_confirmed_session(sid, "ticketing")

    preview = (await client.post(f"/sessions/{sid}/preview")).json()
    assert preview["bundle_key"] == "ticketing"
    assert preview["preview_type"] == "confirmed"

    # Use only v1 keys (no manifest) to drive the app request
    v1_keys = set(v1_fixture.keys())
    request_body = {k: preview[k] for k in v1_keys if k in preview}

    app_payload = (
        await client.post(f"/sessions/{sid}/app", json=request_body)
    ).json()

    assert app_payload["bundle_key"] == "ticketing"
    assert app_payload["preview_type"] == "confirmed"
    assert "manifest" in app_payload
