"""Unit tests for dashboard/client.py — DashboardClient."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from agents.preview_generator.dashboard.auth import KnitAuthService
from agents.preview_generator.dashboard.client import DashboardClient

_BASE_URL = "https://dashboard.example.com"
_GENERATE_URL = f"{_BASE_URL}/api/v1/dashboards/generate/"

_SUCCESS_RESPONSE = {
    "success": True,
    "dashboard": {"id": "42", "name": "Test Dashboard", "url": "/dashboard/42"},
    "widgets": {"total": 5},
    "debug_payload": {
        "widgets": [{"id": 1, "name": "Widget A", "typeId": 1}]
    },
}


def _make_auth(token: str | None = "tok-valid") -> MagicMock:
    auth = MagicMock(spec=KnitAuthService)
    auth.get_token.return_value = token
    return auth


def _make_http_response(status_code: int, body: dict) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.is_success = 200 <= status_code < 300
    resp.json.return_value = body
    resp.text = str(body)
    return resp


@pytest.fixture
def auth() -> MagicMock:
    return _make_auth()


@pytest.fixture
def client(auth: MagicMock) -> DashboardClient:
    return DashboardClient(base_url=_BASE_URL, auth_service=auth)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_generate_returns_response_on_success(client: DashboardClient, auth: MagicMock):
    resp = _make_http_response(200, _SUCCESS_RESPONSE)
    with patch("httpx.post", return_value=resp):
        result = client.generate({"dashboard_name": "Test"})

    assert result is not None
    assert result["success"] is True
    assert result["dashboard"]["id"] == "42"


def test_generate_posts_to_correct_url(client: DashboardClient):
    resp = _make_http_response(200, _SUCCESS_RESPONSE)
    with patch("httpx.post", return_value=resp) as mock_post:
        client.generate({"dashboard_name": "Test"})

    call_args = mock_post.call_args
    assert call_args[0][0] == _GENERATE_URL


def test_generate_sends_bearer_token(client: DashboardClient):
    resp = _make_http_response(200, _SUCCESS_RESPONSE)
    with patch("httpx.post", return_value=resp) as mock_post:
        client.generate({"key": "val"})

    headers = mock_post.call_args[1]["headers"]
    assert headers["Authorization"] == "Bearer tok-valid"


# ---------------------------------------------------------------------------
# No auth token — short-circuit
# ---------------------------------------------------------------------------


def test_generate_returns_none_when_no_token():
    auth = _make_auth(token=None)
    client = DashboardClient(_BASE_URL, auth)
    with patch("httpx.post") as mock_post:
        result = client.generate({})
    assert result is None
    mock_post.assert_not_called()


# ---------------------------------------------------------------------------
# 401 — invalidate + retry
# ---------------------------------------------------------------------------


def test_generate_retries_once_on_401(auth: MagicMock):
    auth.get_token.side_effect = ["tok-expired", "tok-fresh"]
    client = DashboardClient(_BASE_URL, auth)

    resp_401 = _make_http_response(401, {"detail": "Unauthorized"})
    resp_200 = _make_http_response(200, _SUCCESS_RESPONSE)

    with patch("httpx.post", side_effect=[resp_401, resp_200]):
        result = client.generate({})

    auth.invalidate.assert_called_once()
    assert result is not None
    assert result["success"] is True


def test_generate_returns_none_on_double_401(auth: MagicMock):
    auth.get_token.side_effect = ["tok-a", "tok-b"]
    client = DashboardClient(_BASE_URL, auth)

    resp_401 = _make_http_response(401, {"detail": "Unauthorized"})
    with patch("httpx.post", side_effect=[resp_401, resp_401]):
        result = client.generate({})

    assert result is None


# ---------------------------------------------------------------------------
# HTTP errors
# ---------------------------------------------------------------------------


def test_generate_returns_none_on_500(client: DashboardClient):
    resp = _make_http_response(500, {"detail": "server error"})
    with patch("httpx.post", return_value=resp):
        result = client.generate({})
    assert result is None


def test_generate_returns_none_on_404(client: DashboardClient):
    resp = _make_http_response(404, {"detail": "not found"})
    with patch("httpx.post", return_value=resp):
        result = client.generate({})
    assert result is None


def test_generate_returns_none_when_success_false(client: DashboardClient):
    body = {"success": False, "error": "invalid payload"}
    resp = _make_http_response(200, body)
    with patch("httpx.post", return_value=resp):
        result = client.generate({})
    assert result is None


# ---------------------------------------------------------------------------
# Network / timeout errors
# ---------------------------------------------------------------------------


def test_generate_returns_none_on_timeout(client: DashboardClient):
    with patch("httpx.post", side_effect=httpx.TimeoutException("timed out")):
        result = client.generate({})
    assert result is None


def test_generate_returns_none_on_connect_error(client: DashboardClient):
    with patch("httpx.post", side_effect=httpx.ConnectError("unreachable")):
        result = client.generate({})
    assert result is None


def test_generate_returns_none_on_read_error(client: DashboardClient):
    with patch("httpx.post", side_effect=httpx.ReadError("read failed")):
        result = client.generate({})
    assert result is None


# ---------------------------------------------------------------------------
# Base URL normalisation
# ---------------------------------------------------------------------------


def test_base_url_trailing_slash_is_stripped():
    auth = _make_auth()
    client = DashboardClient(base_url=_BASE_URL + "/", auth_service=auth)
    resp = _make_http_response(200, _SUCCESS_RESPONSE)
    with patch("httpx.post", return_value=resp) as mock_post:
        client.generate({})
    assert mock_post.call_args[0][0] == _GENERATE_URL
