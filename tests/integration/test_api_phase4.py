from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass

import pytest
from api.routes import onboarding as onboarding_route
from httpx import ASGITransport, AsyncClient

from api.app import create_app


@dataclass
class TestSettings:
    DEBUG: bool = False
    JWT_SECRET: str = "test-secret"
    JWT_ALGORITHM: str = "HS256"
    RATE_LIMIT_PER_MINUTE: int = 60


async def _fake_database_initialize() -> None:
    return None


async def _fake_database_close() -> None:
    return None


def _fake_pinecone_initialize() -> None:
    return None


async def _fake_pinecone_close() -> None:
    return None


def _patch_infrastructure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("api.app.Database.initialize", _fake_database_initialize)
    monkeypatch.setattr("api.app.Database.close", _fake_database_close)
    monkeypatch.setattr("api.app.pinecone_client.initialize", _fake_pinecone_initialize)
    monkeypatch.setattr("api.app.pinecone_client.close", _fake_pinecone_close)


def _patch_settings(monkeypatch: pytest.MonkeyPatch, settings: TestSettings) -> None:
    monkeypatch.setattr("api.middleware.auth.get_settings", lambda: settings)
    monkeypatch.setattr("api.middleware.rate_limiter.get_settings", lambda: settings)


def _encode_segment(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(encoded).decode("utf-8").rstrip("=")


def _build_jwt_token(secret: str, user_id: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": user_id,
        "exp": int(time.time()) + 300,
        "role_permissions": {"onboarding_access": True},
    }
    signing_input = f"{_encode_segment(header)}.{_encode_segment(payload)}"
    signature = hmac.new(
        secret.encode("utf-8"),
        signing_input.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    signature_segment = base64.urlsafe_b64encode(signature).decode("utf-8").rstrip("=")
    return f"{signing_input}.{signature_segment}"


@pytest.mark.asyncio
async def test_health_route_reports_component_checks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = TestSettings(DEBUG=False)
    _patch_infrastructure(monkeypatch)
    _patch_settings(monkeypatch, settings)

    async def fake_db_health() -> bool:
        return True

    async def fake_pinecone_health() -> bool:
        return True

    monkeypatch.setattr("api.routes.health.Database.health_check", fake_db_health)
    monkeypatch.setattr(
        "api.routes.health.pinecone_client.health_check",
        fake_pinecone_health,
    )

    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "checks": {"database": True, "pinecone": True},
    }


@pytest.mark.asyncio
async def test_onboard_route_passes_auth_context_to_processor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = TestSettings(DEBUG=False)
    _patch_infrastructure(monkeypatch)
    _patch_settings(monkeypatch, settings)

    captured: dict[str, object] = {}

    async def fake_start_session(
        message: str,
        user_id: str | None = None,
        auth_token: str | None = None,
    ) -> dict[str, object]:
        captured["message"] = message
        captured["user_id"] = user_id
        captured["auth_token"] = auth_token
        return {"status": "in_progress", "session_id": "session-1", "message": "ok"}

    monkeypatch.setattr(onboarding_route.PROCESSOR, "start_session", fake_start_session)

    token = _build_jwt_token(settings.JWT_SECRET, "user-123")
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/onboard",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": "I run a 12-person tech agency"},
        )

    assert response.status_code == 200
    assert captured["message"] == "I run a 12-person tech agency"
    assert captured["user_id"] == "user-123"
    assert captured["auth_token"] == token


@pytest.mark.asyncio
async def test_onboard_route_rejects_missing_authorization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = TestSettings(DEBUG=False)
    _patch_infrastructure(monkeypatch)
    _patch_settings(monkeypatch, settings)

    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/onboard",
            json={"message": "I run a 12-person tech agency"},
        )

    assert response.status_code == 401
    assert response.json()["detail"]


@pytest.mark.asyncio
async def test_rate_limiter_blocks_second_request_within_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = TestSettings(DEBUG=True, RATE_LIMIT_PER_MINUTE=1)
    _patch_infrastructure(monkeypatch)
    _patch_settings(monkeypatch, settings)

    async def fake_start_session(
        message: str,
        user_id: str | None = None,
        auth_token: str | None = None,
    ) -> dict[str, object]:
        _ = (message, user_id, auth_token)
        return {"status": "in_progress", "session_id": "session-1", "message": "ok"}

    monkeypatch.setattr(onboarding_route.PROCESSOR, "start_session", fake_start_session)

    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        first_response = await client.post(
            "/onboard",
            json={"message": "first"},
        )
        second_response = await client.post(
            "/onboard",
            json={"message": "second"},
        )

    assert first_response.status_code == 200
    assert second_response.status_code == 429


@pytest.mark.asyncio
async def test_onboard_reply_route_calls_processor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = TestSettings(DEBUG=True)
    _patch_infrastructure(monkeypatch)
    _patch_settings(monkeypatch, settings)

    captured: dict[str, object] = {}

    async def fake_reply(session_id: str, message: str) -> dict[str, object]:
        captured["session_id"] = session_id
        captured["message"] = message
        return {
            "status": "awaiting_input",
            "session_id": session_id,
            "interrupt": {"question": "How many people are in your team?"},
        }

    monkeypatch.setattr(onboarding_route.PROCESSOR, "reply", fake_reply)

    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/onboard/session-1/reply",
            json={"message": "12"},
        )

    assert response.status_code == 200
    assert captured == {"session_id": "session-1", "message": "12"}
