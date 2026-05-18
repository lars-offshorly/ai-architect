from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi import HTTPException, Request

import api.middleware.auth as auth_module
from api.middleware.auth import UserSchema, is_authenticated
from core.config import Settings, get_settings


class FakeRedis:
    def __init__(self, values: dict[str, str]) -> None:
        self.values = values
        self.accessed_keys: list[str] = []

    async def get(self, key: str) -> str | None:
        self.accessed_keys.append(key)
        return self.values.get(key)


def _double_encoded_cache_entry(user: dict[str, Any]) -> str:
    return json.dumps(json.dumps({"user": user}))


def _request(authorization: str | None = None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if authorization is not None:
        headers.append((b"authorization", authorization.encode()))
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/sessions",
            "headers": headers,
            "query_string": b"",
            "server": ("testserver", 80),
            "scheme": "http",
            "client": ("testclient", 50000),
        },
    )


@pytest.fixture(autouse=True)
def _clear_settings_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setattr(
        "api.middleware.auth.get_settings",
        lambda: Settings(DEV_BYPASS=False),
    )


async def test_valid_bearer_token_returns_user_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_redis = FakeRedis(
        {
            ":1:token-123": _double_encoded_cache_entry(
                {"id": 42, "role_permissions": {"can_generate_apps": True}},
            ),
        },
    )
    monkeypatch.setattr(auth_module, "_get_redis_client", lambda: fake_redis)

    user = await is_authenticated(_request(authorization="Bearer token-123"))

    assert isinstance(user, UserSchema)
    assert user.id == 42
    assert user.token == "token-123"
    assert user.role_permissions == {"can_generate_apps": True}
    assert fake_redis.accessed_keys == [":1:token-123"]


async def test_missing_authorization_header_raises_403(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth_module, "_get_redis_client", lambda: FakeRedis({}))

    with pytest.raises(HTTPException) as exc_info:
        await is_authenticated(_request())
    assert exc_info.value.status_code == 403


async def test_unknown_token_raises_401(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth_module, "_get_redis_client", lambda: FakeRedis({}))

    with pytest.raises(HTTPException) as exc_info:
        await is_authenticated(_request(authorization="Bearer unknown-token"))
    assert exc_info.value.status_code == 401
    assert "Invalid or expired" in exc_info.value.detail


async def test_non_integer_user_id_raises_401(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_redis = FakeRedis(
        {
            ":1:token-123": _double_encoded_cache_entry(
                {"id": "42", "role_permissions": {}},
            ),
        },
    )
    monkeypatch.setattr(auth_module, "_get_redis_client", lambda: fake_redis)

    with pytest.raises(HTTPException) as exc_info:
        await is_authenticated(_request(authorization="Bearer token-123"))
    assert exc_info.value.status_code == 401
    assert "missing user identity" in exc_info.value.detail


async def test_bool_user_id_raises_401(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_redis = FakeRedis(
        {":1:token-123": _double_encoded_cache_entry({"id": True, "role_permissions": {}})},
    )
    monkeypatch.setattr(auth_module, "_get_redis_client", lambda: fake_redis)

    with pytest.raises(HTTPException) as exc_info:
        await is_authenticated(_request(authorization="Bearer token-123"))
    assert exc_info.value.status_code == 401
    assert "missing user identity" in exc_info.value.detail


async def test_dev_bypass_returns_admin_user_without_redis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _redis_must_not_be_called() -> None:
        raise AssertionError("Redis must not be called when DEV_BYPASS is true")

    monkeypatch.setattr(auth_module, "_get_redis_client", _redis_must_not_be_called)
    monkeypatch.setattr(
        "api.middleware.auth.get_settings",
        lambda: Settings(DEV_BYPASS=True),
    )

    user = await is_authenticated(_request())

    assert user.id == 1
    assert user.token == "dev"
    assert user.role_permissions == {"admin": True}


async def test_role_permissions_defaults_to_empty_dict_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_redis = FakeRedis(
        {":1:token-123": _double_encoded_cache_entry({"id": 7})},
    )
    monkeypatch.setattr(auth_module, "_get_redis_client", lambda: fake_redis)

    user = await is_authenticated(_request(authorization="Bearer token-123"))

    assert user.id == 7
    assert user.role_permissions == {}


async def test_invalid_role_permissions_type_defaults_to_empty_dict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_redis = FakeRedis(
        {":1:token-123": _double_encoded_cache_entry({"id": 5, "role_permissions": "admin"})},
    )
    monkeypatch.setattr(auth_module, "_get_redis_client", lambda: fake_redis)

    user = await is_authenticated(_request(authorization="Bearer token-123"))

    assert user.id == 5
    assert user.role_permissions == {}
