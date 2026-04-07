"""Unit tests for preview router helpers — bundle key resolution."""

from __future__ import annotations

from domain.models.session import Session
from api.routers.preview import _resolve_early_bundle_key


def _make_session(**kwargs: object) -> Session:
    return Session(**kwargs)


# ---------------------------------------------------------------------------
# _resolve_early_bundle_key — Lars scenarios #1, #2, #3
# ---------------------------------------------------------------------------


def test_selected_bundle_key_wins() -> None:
    """Confirmed selected_bundle_key takes top priority."""
    session = _make_session(
        selected_bundle_key="project_mgmt",
        preselected_bundle_key="ticketing",
        latest_classification={"top_bundle_key": "hr_management"},
    )
    assert _resolve_early_bundle_key(session) == "project_mgmt"


def test_preselected_bundle_key_used_when_no_selected(
) -> None:
    """Lars scenario #1: user chose bundle before chatting."""
    session = _make_session(
        selected_bundle_key=None,
        preselected_bundle_key="ticketing",
        latest_classification={"top_bundle_key": "hr_management"},
    )
    assert _resolve_early_bundle_key(session) == "ticketing"


def test_latest_classification_used_when_no_preselected() -> None:
    """Classifier's best guess mid-conversation is the third fallback."""
    session = _make_session(
        selected_bundle_key=None,
        preselected_bundle_key=None,
        latest_classification={"top_bundle_key": "hr_management"},
    )
    assert _resolve_early_bundle_key(session) == "hr_management"


def test_fallback_bundle_key_when_nothing_set() -> None:
    """Lars scenario #3: 'preview system now' with no classification yet."""
    session = _make_session(
        selected_bundle_key=None,
        preselected_bundle_key=None,
        latest_classification=None,
    )
    assert _resolve_early_bundle_key(session) == "all_microservices"


def test_latest_classification_missing_top_key_falls_to_default() -> None:
    """Malformed classification dict still falls through to default."""
    session = _make_session(
        selected_bundle_key=None,
        preselected_bundle_key=None,
        latest_classification={"confidence": 0.4},  # no top_bundle_key
    )
    assert _resolve_early_bundle_key(session) == "all_microservices"
