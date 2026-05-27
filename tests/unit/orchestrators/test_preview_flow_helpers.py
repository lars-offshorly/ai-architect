from __future__ import annotations

from orchestrators.preview_flow import _last_user_message


def test_returns_last_user_message() -> None:
    history = [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "reply"},
        {"role": "user", "content": "second"},
    ]
    assert _last_user_message(history) == "second"


def test_returns_empty_string_when_no_user_message() -> None:
    history = [{"role": "assistant", "content": "hello"}]
    assert _last_user_message(history) == ""


def test_returns_empty_string_for_empty_history() -> None:
    assert _last_user_message([]) == ""


def test_coerces_non_string_content_to_string() -> None:
    history = [{"role": "user", "content": 42}]
    assert _last_user_message(history) == "42"


def test_handles_missing_content_key() -> None:
    history = [{"role": "user"}]
    assert _last_user_message(history) == ""
