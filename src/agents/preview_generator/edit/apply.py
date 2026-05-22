"""v2 preview edit mutator.

Applies edits against payload.manifest only.
"""

from __future__ import annotations

import copy
import re

from catalog.bundle_catalog import BundleCatalog

from ..schemas import EditAction, EditActionType

_FLAG_TO_MODULE: dict[str, str] = {
    "projects-module": "Projects",
    "tickets-module": "Tickets",
    "hrhub-module": "HRHub",
    "weaves-module": "Weaves",
    "dashboard-module": "Dashboard",
    "kpi-module": "KPI",
    "calendar_module": "Calendar",
    "chat-module": "Chat",
    "ai-toolkit-module": "AIToolkit",
    "rewards-module": "Rewards",
}


def _normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _as_positive_int(target: str | None) -> int | None:
    if target is None:
        return None
    try:
        parsed = int(target)
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def _get_manifest(payload: dict) -> dict | None:
    manifest = payload.get("manifest")
    if not isinstance(manifest, dict):
        return None
    if manifest.get("schema_version") != "2.0":
        return None
    return manifest


def apply_edit(
    payload: dict,
    action: EditAction,
    catalog: BundleCatalog,
) -> tuple[dict, str | None]:
    """Apply v2 edits against payload.manifest (schema_version=2.0)."""
    _ = catalog
    result = copy.deepcopy(payload)

    if action.action_type == EditActionType.UNSUPPORTED:
        warning = (
            f"Unsupported edit instruction: '{action.raw_instruction}'. "
            "No changes were applied."
        )
        result["warning"] = warning
        return result, warning

    manifest = _get_manifest(result)
    if manifest is None:
        warning = "manifest missing or invalid for v2 edit path."
        result["warning"] = warning
        return result, warning

    target_id = _as_positive_int(action.target)
    modules = result.get("modules")
    if not isinstance(modules, list):
        modules = []
        result["modules"] = modules

    if action.action_type in {EditActionType.ADD_MODULE, EditActionType.REMOVE_MODULE}:
        module_name = _FLAG_TO_MODULE.get(action.target or "", action.target)
        if not isinstance(module_name, str) or not module_name:
            return result, "Module edit requires valid module target."
        if action.action_type == EditActionType.REMOVE_MODULE:
            result["modules"] = [m for m in modules if m != module_name]
            return result, None
        if module_name not in modules:
            modules.append(module_name)
        return result, None

    if action.action_type in {EditActionType.ADD_DASHBOARD, EditActionType.REMOVE_DASHBOARD}:
        if action.target == "dashboard-module":
            module_name = _FLAG_TO_MODULE["dashboard-module"]
            if action.action_type == EditActionType.REMOVE_DASHBOARD:
                result["modules"] = [m for m in modules if m != module_name]
                return result, None
            if module_name not in modules:
                modules.append(module_name)
            return result, None

        target_name = (action.target or "").strip()
        if not target_name:
            return result, "Dashboard edit requires target name."
        target_norm = _normalize_name(target_name)

        dashboard_section = manifest.setdefault("dashboard", {})
        dashboards = dashboard_section.setdefault("dashboards", [])
        if not isinstance(dashboards, list):
            dashboards = []
            dashboard_section["dashboards"] = dashboards

        if action.action_type == EditActionType.REMOVE_DASHBOARD:
            before = len(dashboards)
            dashboard_section["dashboards"] = [
                item
                for item in dashboards
                if not (
                    isinstance(item, dict)
                    and isinstance(item.get("name"), str)
                    and _normalize_name(item["name"]) == target_norm
                )
            ]
            if len(dashboard_section["dashboards"]) == before:
                return result, f"Dashboard '{target_name}' not found in manifest."
            return result, None

        if any(
            isinstance(item, dict)
            and isinstance(item.get("name"), str)
            and _normalize_name(item["name"]) == target_norm
            for item in dashboards
        ):
            return result, None
        return result, (
            f"Dashboard '{target_name}' not found in manifest catalog refs. "
            "Use exact dashboard name or dashboard ID."
        )

    if action.action_type in {EditActionType.ADD_QUEUE, EditActionType.REMOVE_QUEUE}:
        if target_id is None:
            return result, "Queue edit requires positive integer target id."
        ticket_section = manifest.setdefault("tickets", {})
        queues = ticket_section.setdefault("queues", [])
        if not isinstance(queues, list):
            queues = []
            ticket_section["queues"] = queues
        if action.action_type == EditActionType.REMOVE_QUEUE:
            ticket_section["queues"] = [
                queue
                for queue in queues
                if not (isinstance(queue, dict) and queue.get("id") == target_id)
            ]
            return result, None
        if not any(
            isinstance(queue, dict) and queue.get("id") == target_id for queue in queues
        ):
            queues.append({"id": target_id, "name": f"Queue {target_id}"})
        return result, None

    if action.action_type in {
        EditActionType.ADD_DASHBOARD_BY_ID,
        EditActionType.REMOVE_DASHBOARD_BY_ID,
    }:
        if target_id is None:
            return result, "Dashboard edit requires positive integer target id."
        dashboard_section = manifest.setdefault("dashboard", {})
        dashboards = dashboard_section.setdefault("dashboards", [])
        if not isinstance(dashboards, list):
            dashboards = []
            dashboard_section["dashboards"] = dashboards
        if action.action_type == EditActionType.REMOVE_DASHBOARD_BY_ID:
            dashboard_section["dashboards"] = [
                item
                for item in dashboards
                if not (isinstance(item, dict) and item.get("id") == target_id)
            ]
            return result, None
        if not any(
            isinstance(item, dict) and item.get("id") == target_id for item in dashboards
        ):
            dashboards.append({"id": target_id, "name": f"Dashboard {target_id}"})
        return result, None

    warning = (
        f"Unsupported v2 edit action: '{action.action_type.value}'. "
        "Supported actions: module toggle, add/remove queue by id, "
        "add/remove dashboard by id, add/remove dashboard by name."
    )
    result["warning"] = warning
    return result, warning
