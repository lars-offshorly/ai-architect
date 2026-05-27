"""Deterministic SelectionResult + manifest -> tenant-provisioning JSON.

This is the only piece of the v2 path with no LLM dependency. It is a pure
function of (manifest, selection, session_id, generated_at). Given the same
inputs it produces byte-identical output, which is what makes it trivially
testable with golden fixtures.

Semantic checks performed here (in addition to schema-level ones already done
by SelectionResult):

* ``tenant.industry`` must equal the manifest's industry (design decision 1).
* Every ``selected_*_id`` must exist in the corresponding catalog list.
* Every ``EmployeeOverride.id`` must reference a real catalog employee.

Output order matches manifest order, not selection order, so reviewers see a
stable layout regardless of how the LLM happened to list things.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .schemas import SelectionResult


class EmitterError(ValueError):
    """Raised when a SelectionResult cannot be emitted against a manifest."""


def emit_tenant_provisioning(
    manifest: dict[str, Any],
    selection: SelectionResult,
    *,
    session_id: str,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Project (manifest, selection) into the final tenant-provisioning JSON.

    ``generated_at`` defaults to ``datetime.now(timezone.utc)`` when omitted.
    The function never mutates ``manifest``.
    """
    _check_industry(manifest, selection)

    timestamp = (generated_at or datetime.now(timezone.utc)).isoformat()
    if timestamp.endswith("+00:00"):
        timestamp = timestamp[:-6] + "Z"

    return {
        "schema_version": manifest.get("schema_version", "2.0"),
        "session_id": session_id,
        "generated_at": timestamp,
        "tenant": selection.tenant.model_dump(),
        "tickets": {
            "queues": _filter_items(
                manifest, "tickets", "queues", selection.selected_queue_ids
            ),
        },
        "projects": {
            "projects": _filter_items(
                manifest, "projects", "projects", selection.selected_project_ids
            ),
        },
        "dashboard": {
            "dashboards": _filter_items(
                manifest, "dashboard", "dashboards", selection.selected_dashboard_ids
            ),
        },
        "kpi": {
            "kpis": _filter_items(manifest, "kpi", "kpis", selection.selected_kpi_ids),
        },
        "hr_hub": {
            "employees": _filter_employees(manifest, selection),
            "request_types": _filter_items(
                manifest,
                "hr_hub",
                "request_types",
                selection.selected_request_type_ids,
            ),
        },
    }


def _check_industry(manifest: dict[str, Any], selection: SelectionResult) -> None:
    manifest_industry = manifest.get("tenant", {}).get("industry")
    if manifest_industry != selection.tenant.industry:
        raise EmitterError(
            "tenant.industry must equal the routing industry "
            f"(manifest='{manifest_industry}', selection='{selection.tenant.industry}')"
        )


def _filter_items(
    manifest: dict[str, Any],
    section: str,
    array_key: str,
    selected_ids: list[int],
) -> list[dict[str, Any]]:
    raw = manifest.get(section, {}).get(array_key, [])
    if not isinstance(raw, list):
        raise EmitterError(f"manifest {section}.{array_key} must be a list")

    catalog_ids = {entry["id"] for entry in raw if isinstance(entry, dict)}
    missing = sorted(set(selected_ids) - catalog_ids)
    if missing:
        raise EmitterError(
            f"{section}.{array_key} selection references unknown ids: {missing}"
        )

    wanted = set(selected_ids)
    return [
        {"id": entry["id"], "name": entry["name"]}
        for entry in raw
        if isinstance(entry, dict) and entry.get("id") in wanted
    ]


def _filter_employees(
    manifest: dict[str, Any], selection: SelectionResult
) -> list[dict[str, Any]]:
    raw = manifest.get("hr_hub", {}).get("employees", [])
    if not isinstance(raw, list):
        raise EmitterError("manifest hr_hub.employees must be a list")

    catalog: dict[int, dict[str, Any]] = {}
    for entry in raw:
        if isinstance(entry, dict) and isinstance(entry.get("id"), int):
            catalog[entry["id"]] = entry

    missing_selected = sorted(set(selection.selected_employee_ids) - catalog.keys())
    if missing_selected:
        raise EmitterError(
            f"hr_hub.employees selection references unknown ids: {missing_selected}"
        )

    overrides_by_id = {o.id: o for o in selection.employee_overrides}
    missing_overrides = sorted(overrides_by_id.keys() - catalog.keys())
    if missing_overrides:
        raise EmitterError(
            f"employee_overrides reference unknown catalog ids: {missing_overrides}"
        )

    wanted = set(selection.selected_employee_ids)
    result: list[dict[str, Any]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        emp_id = entry.get("id")
        if emp_id not in wanted:
            continue
        override = overrides_by_id.get(emp_id)
        if override is None:
            result.append(
                {
                    "id": emp_id,
                    "position": entry.get("position", ""),
                    "team": entry.get("team", ""),
                    "department": entry.get("department", ""),
                    "job_title": entry.get("job_title", ""),
                    "job_type": entry.get("job_type", ""),
                    "job_level": entry.get("job_level", ""),
                }
            )
        else:
            result.append(
                {
                    "id": emp_id,
                    "position": override.position,
                    "team": override.team,
                    "department": override.department,
                    "job_title": override.job_title,
                    "job_type": override.job_type,
                    "job_level": override.job_level,
                }
            )
    return result
