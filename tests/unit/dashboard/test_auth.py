"""Unit tests for dashboard/auth.py — KnitAuthService."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import httpx
import pytest

from agents.preview_generator.dashboard.auth import KnitAuthService

_URL = "https://auth.example.com/login/"
_EMAIL = "user@example.com"
_PASSWORD = "secret"


@pytest.fixture
def auth() -> KnitAuthService:
    return KnitAuthService(_URL, _EMAIL, _PASSWORD, ttl_seconds=60)


def _mock_response(token_value: str, field: str = "token") -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.raise_for_status.return_value = None
    resp.json.return_value = {field: token_value}
    return resp


# ---------------------------------------------------------------------------
# Credential validation
# ---------------------------------------------------------------------------


def test_raises_on_empty_email():
    with pytest.raises(ValueError, match="KNIT_EMAIL"):
        KnitAuthService(_URL, "", _PASSWORD)


def test_raises_on_empty_password():
    with pytest.raises(ValueError, match="KNIT_PASSWORD"):
        KnitAuthService(_URL, _EMAIL, "")


def test_raises_on_empty_url():
    with pytest.raises(ValueError, match="KNIT_AUTH_URL"):
        KnitAuthService("", _EMAIL, _PASSWORD)


# ---------------------------------------------------------------------------
# Happy path — token fetch and caching
# ---------------------------------------------------------------------------


def test_get_token_returns_token_on_success(auth: KnitAuthService):
    with patch("httpx.post", return_value=_mock_response("tok-abc")):
        token = auth.get_token()
    assert token == "tok-abc"


def test_get_token_caches_within_ttl(auth: KnitAuthService):
    with patch("httpx.post", return_value=_mock_response("tok-cached")) as mock_post:
        auth.get_token()
        auth.get_token()
    # Only one HTTP call despite two get_token() calls
    assert mock_post.call_count == 1


def test_get_token_refreshes_after_ttl_expiry(auth: KnitAuthService):
    with patch("httpx.post", return_value=_mock_response("tok-first")):
        auth.get_token()

    # Force expiry
    auth._expires_at = time.monotonic() - 1

    with patch("httpx.post", return_value=_mock_response("tok-second")) as mock_post:
        token = auth.get_token()

    assert token == "tok-second"
    assert mock_post.call_count == 1


def test_invalidate_forces_refresh(auth: KnitAuthService):
    with patch("httpx.post", return_value=_mock_response("tok-v1")):
        auth.get_token()

    auth.invalidate()

    with patch("httpx.post", return_value=_mock_response("tok-v2")) as mock_post:
        token = auth.get_token()

    assert token == "tok-v2"
    assert mock_post.call_count == 1


# ---------------------------------------------------------------------------
# Failure modes — stale token fallback
# ---------------------------------------------------------------------------


def test_network_error_returns_stale_token(auth: KnitAuthService):
    # Prime with a valid token
    with patch("httpx.post", return_value=_mock_response("tok-stale")):
        auth.get_token()
    auth._expires_at = time.monotonic() - 1  # force expiry

    with patch("httpx.post", side_effect=httpx.ConnectError("unreachable")):
        token = auth.get_token()

    assert token == "tok-stale"


def test_http_error_returns_stale_token(auth: KnitAuthService):
    with patch("httpx.post", return_value=_mock_response("tok-stale")):
        auth.get_token()
    auth._expires_at = time.monotonic() - 1

    bad_resp = MagicMock(spec=httpx.Response)
    bad_resp.status_code = 401
    bad_resp.text = "Unauthorized"
    bad_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "401", request=MagicMock(), response=bad_resp
    )
    with patch("httpx.post", return_value=bad_resp):
        token = auth.get_token()

    assert token == "tok-stale"


def test_first_call_network_error_returns_none(auth: KnitAuthService):
    with patch("httpx.post", side_effect=httpx.ConnectError("down")):
        token = auth.get_token()
    assert token is None


# ---------------------------------------------------------------------------
# _parse_token — field name variants
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload, expected",
    [
        ({"token": "tok-a"}, "tok-a"),
        ({"access_token": "tok-b"}, "tok-b"),
        ({"key": "tok-c"}, "tok-c"),
        ({"data": {"token": "tok-d"}}, "tok-d"),
        ({"data": {"access_token": "tok-e"}}, "tok-e"),
        ({"data": {"key": "tok-f"}}, "tok-f"),
    ],
)
def test_parse_token_variants(payload: dict, expected: str):
    result = KnitAuthService._parse_token(payload)
    assert result == expected


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"other_field": "value"},
        {"token": ""},
        {"token": None},
        {"data": {}},
        "not-a-dict",
        None,
    ],
)
def test_parse_token_returns_none_for_unrecognised(payload):
    result = KnitAuthService._parse_token(payload)
    assert result is None
