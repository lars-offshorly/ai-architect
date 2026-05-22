"""Unit tests for apply_edit — dashboard operations against payload.manifest."""

from __future__ import annotations

from agents.preview_generator.edit.apply import apply_edit
from agents.preview_generator.schemas import EditAction, EditActionType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_payload(
    dashboards: list[dict] | None = None,
    modules: list[str] | None = None,
) -> dict:
    return {
        "schema_version": "2.0",
        "session_id": "sess-1",
        "bundle_key": "hr_management",
        "modules": modules if modules is not None else ["Dashboard"],
        "manifest": {
            "schema_version": "2.0",
            "session_id": "sess-1",
            "dashboard": {
                "dashboards": dashboards
                if dashboards is not None
                else [{"id": 703, "name": "Workforce & Attrition"}]
            },
        },
    }


def _action(action_type: EditActionType, target: str | None = None) -> EditAction:
    return EditAction(action_type=action_type, target=target, raw_instruction="")


# ---------------------------------------------------------------------------
# Module toggle
# ---------------------------------------------------------------------------


def test_remove_dashboard_module_toggle() -> None:
    payload = _make_payload(modules=["Dashboard", "KPI"])
    result, warning = apply_edit(payload, _action(EditActionType.REMOVE_DASHBOARD, "dashboard-module"), catalog=None)  # type: ignore[arg-type]
    assert "Dashboard" not in result["modules"]
    assert warning is None


def test_add_dashboard_module_toggle() -> None:
    payload = _make_payload(modules=["KPI"])
    result, warning = apply_edit(payload, _action(EditActionType.ADD_DASHBOARD, "dashboard-module"), catalog=None)  # type: ignore[arg-type]
    assert "Dashboard" in result["modules"]
    assert warning is None


# ---------------------------------------------------------------------------
# By ID
# ---------------------------------------------------------------------------


def test_remove_dashboard_by_id() -> None:
    payload = _make_payload(dashboards=[{"id": 703, "name": "Workforce & Attrition"}, {"id": 704, "name": "Ops"}])
    result, warning = apply_edit(payload, _action(EditActionType.REMOVE_DASHBOARD_BY_ID, "703"), catalog=None)  # type: ignore[arg-type]
    remaining_ids = [d["id"] for d in result["manifest"]["dashboard"]["dashboards"]]
    assert 703 not in remaining_ids
    assert 704 in remaining_ids
    assert warning is None


# ---------------------------------------------------------------------------
# By name
# ---------------------------------------------------------------------------


def test_remove_dashboard_by_name() -> None:
    payload = _make_payload(dashboards=[{"id": 703, "name": "Workforce & Attrition"}, {"id": 704, "name": "Ops"}])
    result, warning = apply_edit(payload, _action(EditActionType.REMOVE_DASHBOARD, "Workforce & Attrition"), catalog=None)  # type: ignore[arg-type]
    remaining_names = [d["name"] for d in result["manifest"]["dashboard"]["dashboards"]]
    assert "Workforce & Attrition" not in remaining_names
    assert "Ops" in remaining_names
    assert warning is None


def test_remove_unknown_dashboard_name_returns_warning() -> None:
    payload = _make_payload(dashboards=[{"id": 703, "name": "Workforce & Attrition"}])
    result, warning = apply_edit(payload, _action(EditActionType.REMOVE_DASHBOARD, "Nonexistent Dashboard"), catalog=None)  # type: ignore[arg-type]
    assert warning is not None
    assert "Nonexistent Dashboard" in warning
    assert len(result["manifest"]["dashboard"]["dashboards"]) == 1
