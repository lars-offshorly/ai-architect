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

_ALLOWED_ACTIONS: set[EditActionType] = {
    EditActionType.ADD_MODULE,
    EditActionType.REMOVE_MODULE,
    EditActionType.ADD_QUEUE,
    EditActionType.REMOVE_QUEUE,
    EditActionType.ADD_DASHBOARD,
    EditActionType.REMOVE_DASHBOARD,
    EditActionType.ADD_DASHBOARD_BY_ID,
    EditActionType.REMOVE_DASHBOARD_BY_ID,
    EditActionType.ADD_KPI,
    EditActionType.REMOVE_KPI,
}

_FROZEN_MANIFEST_SECTIONS = {"tenant", "projects", "hr_hub"}


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


def _resolve_ref_by_name(
    refs: list[dict],
    target_name: str,
) -> tuple[dict | None, str | None]:
    normalized_target = _normalize_name(target_name)
    if not normalized_target:
        return None, "Target name is empty."

    exact_matches = [
        ref
        for ref in refs
        if isinstance(ref, dict)
        and isinstance(ref.get("name"), str)
        and _normalize_name(ref["name"]) == normalized_target
    ]
    if len(exact_matches) == 1:
        return exact_matches[0], None
    if len(exact_matches) > 1:
        names = [str(item.get("name")) for item in exact_matches]
        return None, f"Ambiguous target '{target_name}'. Matches: {', '.join(names)}."

    partial_matches = [
        ref
        for ref in refs
        if isinstance(ref, dict)
        and isinstance(ref.get("name"), str)
        and normalized_target in _normalize_name(ref["name"])
    ]
    if len(partial_matches) == 1:
        return partial_matches[0], None
    if len(partial_matches) > 1:
        names = [str(item.get("name")) for item in partial_matches]
        return None, f"Ambiguous target '{target_name}'. Matches: {', '.join(names)}."
    return None, f"Target '{target_name}' not found."


def _warn(code: str, message: str) -> str:
    return f"{code}: {message}"


def _policy_denied(action: EditActionType) -> str:
    return _warn(
        "policy_violation",
        (
            f"Action '{action.value}' is not allowed. Allowed actions: "
            "module toggle, add/remove queue, add/remove dashboard, add/remove KPI."
        ),
    )


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
    if action.action_type not in _ALLOWED_ACTIONS:
        warning = _policy_denied(action.action_type)
        result["warning"] = warning
        return result, warning

    manifest = _get_manifest(result)
    if manifest is None:
        warning = _warn("manifest_invalid", "manifest missing or invalid for edit path.")
        result["warning"] = warning
        return result, warning
    for section in _FROZEN_MANIFEST_SECTIONS:
        if section not in manifest:
            warning = _warn(
                "manifest_invalid",
                f"manifest missing required frozen section '{section}'.",
            )
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
            return result, _warn("invalid_target", "Module edit requires valid module target.")
        if action.action_type == EditActionType.REMOVE_MODULE:
            result["modules"] = [m for m in modules if m != module_name]
            return result, None
        if module_name not in modules:
            modules.append(module_name)
        return result, None

    if action.action_type in {
        EditActionType.ADD_DASHBOARD,
        EditActionType.REMOVE_DASHBOARD,
    }:
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
            return result, _warn("invalid_target", "Dashboard edit requires target name.")

        dashboard_section = manifest.setdefault("dashboard", {})
        dashboards = dashboard_section.setdefault("dashboards", [])
        if not isinstance(dashboards, list):
            dashboards = []
            dashboard_section["dashboards"] = dashboards

        resolved, warning = _resolve_ref_by_name(dashboards, target_name)
        if action.action_type == EditActionType.REMOVE_DASHBOARD:
            if warning is not None or resolved is None:
                return result, _warn("resolution_failed", f"Dashboard edit failed: {warning}")
            resolved_id = resolved.get("id")
            dashboard_section["dashboards"] = [
                item
                for item in dashboards
                if not (isinstance(item, dict) and item.get("id") == resolved_id)
            ]
            return result, None

        if warning is None and resolved is not None:
            return result, None
        return result, _warn("resolution_failed", f"Dashboard edit failed: {warning}")

    if action.action_type in {EditActionType.ADD_QUEUE, EditActionType.REMOVE_QUEUE}:
        ticket_section = manifest.setdefault("tickets", {})
        queues = ticket_section.setdefault("queues", [])
        if not isinstance(queues, list):
            queues = []
            ticket_section["queues"] = queues
        if target_id is None:
            target_name = (action.target or "").strip()
            resolved, warning = _resolve_ref_by_name(queues, target_name)
            if warning is not None or resolved is None:
                return result, _warn("resolution_failed", f"Queue edit failed: {warning}")
            target_id = _as_positive_int(str(resolved.get("id")))
            if target_id is None:
                return result, _warn(
                    "invalid_target", "Queue edit failed: resolved queue has invalid id."
                )
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

    if action.action_type in {EditActionType.ADD_KPI, EditActionType.REMOVE_KPI}:
        kpi_section = manifest.setdefault("kpi", {})
        kpis = kpi_section.setdefault("kpis", [])
        if not isinstance(kpis, list):
            kpis = []
            kpi_section["kpis"] = kpis

        kpi_id = target_id
        if kpi_id is None:
            target_name = (action.target or "").strip()
            resolved, warning = _resolve_ref_by_name(kpis, target_name)
            if warning is not None or resolved is None:
                return result, _warn("resolution_failed", f"KPI edit failed: {warning}")
            kpi_id = _as_positive_int(str(resolved.get("id")))
            if kpi_id is None:
                return result, _warn(
                    "invalid_target", "KPI edit failed: resolved KPI has invalid id."
                )

        if action.action_type == EditActionType.REMOVE_KPI:
            kpi_section["kpis"] = [
                item
                for item in kpis
                if not (isinstance(item, dict) and item.get("id") == kpi_id)
            ]
            return result, None
        if not any(isinstance(item, dict) and item.get("id") == kpi_id for item in kpis):
            kpis.append({"id": kpi_id, "name": f"KPI {kpi_id}"})
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
