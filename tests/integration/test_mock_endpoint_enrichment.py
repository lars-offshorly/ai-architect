"""Integration tests: /mock endpoint returns preview-shaped payloads.

Ensures mock previews run through PreviewFlow so they include:
- static bundle template overlay
- static dashboard widget injection + patched dashboard_generation_output
"""

from __future__ import annotations

import importlib
import os
import sys
import uuid
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture(name="app", scope="module")
def fixture_app():
    sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

    os.environ["DEBUG"] = "True"
    os.environ["ENABLE_MOCK_ENDPOINTS"] = "True"
    os.environ["DISABLE_LLM_CALLS"] = "True"

    config_module = importlib.import_module("core.config")
    config_module.get_settings.cache_clear()
    api_app_module = importlib.import_module("api.app")
    return api_app_module.create_app()


@pytest.fixture(name="client")
async def fixture_client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def _unique_id() -> str:
    return str(uuid.uuid4())


@pytest.mark.asyncio
async def test_mock_payload_includes_static_widgets_and_generation_output(
    client: AsyncClient,
) -> None:
    # Use a canonical bundle key with known templates.
    resp = await client.post(f"/mock/hr_management", json={"session_id": _unique_id()})
    assert resp.status_code == 200, resp.text

    data = resp.json()
    stores = data["dummy_data_json"]["stores"]
    widgets = stores.get("dashboard_widgets")
    assert isinstance(widgets, list)
    assert len(widgets) > 0

    gen_out = stores.get("dashboard_generation_output")
    assert isinstance(gen_out, dict)
    assert gen_out.get("widgets", {}).get("total") == len(widgets)
    assert gen_out.get("dashboard", {}).get("external_id")
