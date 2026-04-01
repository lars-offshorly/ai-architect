"""Unit tests for edit/apply.py — applies EditAction to preview payload."""

from __future__ import annotations

import copy
from typing import Any

from agents.preview_generator.edit.apply import apply_edit
from agents.preview_generator.schemas import EditAction, EditActionType

# ---------------------------------------------------------------------------
# Fixtures — minimal AppPayloadResponseSchema dict
# ---------------------------------------------------------------------------


def _make_payload(
    *,
    modules: list[str] | None = None,
    flag_overrides: dict[str, bool] | None = None,
    kpi_keys: list[str] | None = None,
    stores: dict | None = None,
    config: dict | None = None,
) -> dict:
    """Build a minimal payload dict matching AppPayloadResponseSchema shape."""
    flags: list[dict[str, Any]] = [
        {
            "id": 5,
            "name": "chat-module",
            "description": "Chat Module",
            "isEnabled": True,
            "module": "Global",
        },
        {
            "id": 7,
            "name": "projects-module",
            "description": "Projects Module",
            "isEnabled": True,
            "module": "Global",
        },
        {
            "id": 6,
            "name": "tickets-module",
            "description": "Tickets Module",
            "isEnabled": True,
            "module": "Global",
        },
        {
            "id": 2,
            "name": "dashboard-module",
            "description": "Dashboard Module",
            "isEnabled": True,
            "module": "Global",
        },
        {
            "id": 123,
            "name": "kpi-module",
            "description": "KPI Module",
            "isEnabled": True,
            "module": "Global",
        },
        {
            "id": 3,
            "name": "hrhub-module",
            "description": "Hr Hub Module",
            "isEnabled": False,
            "module": "Global",
        },
        {
            "id": 109,
            "name": "calendar_module",
            "description": "Calendar module",
            "isEnabled": False,
            "module": "Global",
        },
        {
            "id": 4,
            "name": "weaves-module",
            "description": "Weaves Module",
            "isEnabled": False,
            "module": "Global",
        },
        {
            "id": 187,
            "name": "ai-toolkit-module",
            "description": "AI Toolkit Module",
            "isEnabled": False,
            "module": "Global",
        },
    ]
    if flag_overrides:
        for f in flags:
            if f["name"] in flag_overrides:
                f["isEnabled"] = flag_overrides[f["name"]]

    default_kpis = kpi_keys or ["capacity_utilization", "active_work_items"]
    kpis = [
        {
            "key": k,
            "label": k.replace("_", " ").title(),
            "type": "percentage",
            "source_service": "projects",
            "sample_value": 87.5,
        }
        for k in default_kpis
    ]

    default_stores = stores or {
        "kpis": kpis,
        "dashboard_widgets": [],
        "tickets": [{"id": 101, "title": "Test ticket"}],
        "milestones": [{"id": 1, "name": "Phase 1"}],
    }

    default_config = config or {
        "permission_services": ["projects", "kpi"],
        "landing_pages": [],
        "kpi_definitions": default_kpis,
    }

    return {
        "schema_version": "1.0",
        "session_id": "test-session",
        "bundle_key": "project_mgmt",
        "display_name": "Project Management",
        "modules": modules or ["Projects", "Tickets", "Dashboard", "KPI", "Chat"],
        "generation_json": {
            "schema_version": "1.0",
            "bundle_key": "project_mgmt",
            "feature_flags": flags,
            "modules": modules or ["Projects", "Tickets", "Dashboard", "KPI", "Chat"],
            "config": default_config,
        },
        "dummy_data_json": {
            "bundle_key": "project_mgmt",
            "session_id": "test-session",
            "company_name": "TestCo",
            "stores": default_stores,
        },
        "warning": None,
    }


def _action(action_type: EditActionType, target: str | None = None) -> EditAction:
    return EditAction(action_type=action_type, target=target, raw_instruction="test")


# ---------------------------------------------------------------------------
# remove_module
# ---------------------------------------------------------------------------


class TestRemoveModule:
    def test_flag_disabled(self) -> None:
        payload = _make_payload()
        result, _ = apply_edit(
            payload, _action(EditActionType.remove_module, "chat-module")
        )
        flag = next(
            f
            for f in result["generation_json"]["feature_flags"]
            if f["name"] == "chat-module"
        )
        assert flag["isEnabled"] is False

    def test_module_removed_from_list(self) -> None:
        payload = _make_payload()
        result, _ = apply_edit(
            payload, _action(EditActionType.remove_module, "chat-module")
        )
        assert "Chat" not in result["generation_json"]["modules"]
        assert "Chat" not in result["modules"]

    def test_cascading_kpi_removal(self) -> None:
        """Removing tickets-module should remove KPIs sourced from 'tickets'."""
        payload = _make_payload(
            kpi_keys=["avg_resolution_time", "capacity_utilization"],
        )
        # avg_resolution_time source_service = "tickets"
        payload["dummy_data_json"]["stores"]["kpis"][0]["source_service"] = "tickets"
        payload["dummy_data_json"]["stores"]["kpis"][1]["source_service"] = "hr_hub"

        result, _ = apply_edit(
            payload, _action(EditActionType.remove_module, "tickets-module")
        )
        remaining_kpis = result["dummy_data_json"]["stores"]["kpis"]
        kpi_keys = [k["key"] for k in remaining_kpis]
        assert "avg_resolution_time" not in kpi_keys
        assert "capacity_utilization" in kpi_keys

    def test_cascading_store_removal_tickets(self) -> None:
        """Removing tickets-module removes the 'tickets' store."""
        payload = _make_payload()
        result, _ = apply_edit(
            payload, _action(EditActionType.remove_module, "tickets-module")
        )
        assert "tickets" not in result["dummy_data_json"]["stores"]

    def test_cascading_store_removal_projects(self) -> None:
        """Removing projects-module removes project-related stores."""
        payload = _make_payload()
        payload["dummy_data_json"]["stores"]["tasks"] = [{"id": 1}]
        result, _ = apply_edit(
            payload, _action(EditActionType.remove_module, "projects-module")
        )
        assert "tasks" not in result["dummy_data_json"]["stores"]
        assert "milestones" not in result["dummy_data_json"]["stores"]

    def test_idempotent_remove_already_disabled(self) -> None:
        """Removing a module that's already disabled is a no-op."""
        payload = _make_payload(flag_overrides={"calendar_module": False})
        result, _ = apply_edit(
            payload, _action(EditActionType.remove_module, "calendar_module")
        )
        # Should not error, payload essentially unchanged structurally
        assert result["generation_json"]["feature_flags"] is not None

    def test_does_not_mutate_input(self) -> None:
        """apply_edit must not mutate the input payload dict."""
        payload = _make_payload()
        original = copy.deepcopy(payload)
        apply_edit(payload, _action(EditActionType.remove_module, "chat-module"))
        assert payload == original


# ---------------------------------------------------------------------------
# add_module
# ---------------------------------------------------------------------------


class TestAddModule:
    def test_flag_enabled(self) -> None:
        payload = _make_payload(flag_overrides={"calendar_module": False})
        result, _ = apply_edit(
            payload, _action(EditActionType.add_module, "calendar_module")
        )
        flag = next(
            f
            for f in result["generation_json"]["feature_flags"]
            if f["name"] == "calendar_module"
        )
        assert flag["isEnabled"] is True

    def test_module_added_to_list(self) -> None:
        payload = _make_payload(modules=["Projects"])
        result, _ = apply_edit(
            payload, _action(EditActionType.add_module, "calendar_module")
        )
        assert "Calendar" in result["generation_json"]["modules"]
        assert "Calendar" in result["modules"]

    def test_idempotent_add_already_enabled(self) -> None:
        """Adding a module already in the list doesn't duplicate it."""
        payload = _make_payload()
        result, _ = apply_edit(
            payload, _action(EditActionType.add_module, "chat-module")
        )
        assert result["generation_json"]["modules"].count("Chat") == 1


# ---------------------------------------------------------------------------
# remove_kpi
# ---------------------------------------------------------------------------


class TestRemoveKpi:
    def test_kpi_removed_from_stores(self) -> None:
        payload = _make_payload(kpi_keys=["capacity_utilization", "active_work_items"])
        result, _ = apply_edit(
            payload, _action(EditActionType.remove_kpi, "capacity_utilization")
        )
        kpi_keys = [k["key"] for k in result["dummy_data_json"]["stores"]["kpis"]]
        assert "capacity_utilization" not in kpi_keys
        assert "active_work_items" in kpi_keys

    def test_kpi_removed_from_config(self) -> None:
        payload = _make_payload(kpi_keys=["capacity_utilization", "active_work_items"])
        result, _ = apply_edit(
            payload, _action(EditActionType.remove_kpi, "capacity_utilization")
        )
        assert (
            "capacity_utilization"
            not in result["generation_json"]["config"]["kpi_definitions"]
        )

    def test_remove_nonexistent_kpi_is_noop(self) -> None:
        payload = _make_payload(kpi_keys=["capacity_utilization"])
        result, _ = apply_edit(
            payload, _action(EditActionType.remove_kpi, "nonexistent_metric")
        )
        kpi_keys = [k["key"] for k in result["dummy_data_json"]["stores"]["kpis"]]
        assert "capacity_utilization" in kpi_keys


# ---------------------------------------------------------------------------
# add_kpi
# ---------------------------------------------------------------------------


class TestAddKpi:
    def test_kpi_added_to_stores(self) -> None:
        payload = _make_payload(kpi_keys=["capacity_utilization"])
        result, _ = apply_edit(
            payload, _action(EditActionType.add_kpi, "sla_compliance")
        )
        kpi_keys = [k["key"] for k in result["dummy_data_json"]["stores"]["kpis"]]
        assert "sla_compliance" in kpi_keys

    def test_kpi_added_to_config(self) -> None:
        payload = _make_payload(kpi_keys=["capacity_utilization"])
        result, _ = apply_edit(
            payload, _action(EditActionType.add_kpi, "sla_compliance")
        )
        assert (
            "sla_compliance" in result["generation_json"]["config"]["kpi_definitions"]
        )

    def test_add_unknown_kpi_returns_warning(self) -> None:
        payload = _make_payload()
        result, warning = apply_edit(
            payload, _action(EditActionType.add_kpi, "nonexistent_metric")
        )
        assert warning is not None
        assert "not found" in warning.lower() or "unknown" in warning.lower()

    def test_add_duplicate_kpi_is_noop(self) -> None:
        payload = _make_payload(kpi_keys=["capacity_utilization"])
        result, _ = apply_edit(
            payload, _action(EditActionType.add_kpi, "capacity_utilization")
        )
        kpi_keys = [k["key"] for k in result["dummy_data_json"]["stores"]["kpis"]]
        assert kpi_keys.count("capacity_utilization") == 1


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


class TestDashboard:
    def test_remove_dashboard(self) -> None:
        payload = _make_payload()
        result, _ = apply_edit(
            payload, _action(EditActionType.remove_dashboard, "dashboard-module")
        )
        flag = next(
            f
            for f in result["generation_json"]["feature_flags"]
            if f["name"] == "dashboard-module"
        )
        assert flag["isEnabled"] is False
        assert "Dashboard" not in result["generation_json"]["modules"]

    def test_add_dashboard(self) -> None:
        payload = _make_payload(
            modules=["Projects"],
            flag_overrides={"dashboard-module": False},
        )
        result, _ = apply_edit(
            payload, _action(EditActionType.add_dashboard, "dashboard-module")
        )
        flag = next(
            f
            for f in result["generation_json"]["feature_flags"]
            if f["name"] == "dashboard-module"
        )
        assert flag["isEnabled"] is True
        assert "Dashboard" in result["generation_json"]["modules"]


# ---------------------------------------------------------------------------
# Unsupported
# ---------------------------------------------------------------------------


class TestUnsupported:
    def test_returns_original_with_warning(self) -> None:
        payload = _make_payload()
        result, warning = apply_edit(payload, _action(EditActionType.unsupported))
        assert warning is not None
        assert "unsupported" in warning.lower() or "not supported" in warning.lower()
        # Payload structure preserved
        assert result["session_id"] == "test-session"
        assert result["bundle_key"] == "project_mgmt"
