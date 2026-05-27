from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from core.config import get_settings

_ALLOWED_ORIGINS = (
    "http://localhost:3000",
    "http://localhost:3001",
    "https://ai-architect.idealforliving.com",
)


@pytest.fixture(name="client")
def fixture_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DEBUG", "False")
    get_settings.cache_clear()

    return TestClient(create_app())


def test_cors_preflight_allows_configured_origins(client: TestClient) -> None:
    for origin in _ALLOWED_ORIGINS:
        response = client.options(
            "/sessions",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin


def test_unauthorized_response_keeps_cors_header(client: TestClient) -> None:
    response = client.post(
        "/sessions",
        headers={"Origin": "http://localhost:3000"},
        json={},
    )

    assert response.status_code in (
        401,
        403,
        503,
    )  # auth behavior varies by safety-guard env
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
