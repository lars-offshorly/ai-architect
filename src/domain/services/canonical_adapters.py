from __future__ import annotations

from typing import Any


def normalize_manifest_for_runtime(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize a schema-versioned manifest into the runtime canonical shape.

    Runtime canonical shape expects top-level sections:
    ``tenant``, ``tickets.queues``, ``projects.projects``, ``dashboard.dashboards``,
    ``kpi.kpis``, and ``hr_hub.{employees,request_types}``.
    """
    version = payload.get("schema_version")
    if not isinstance(version, str) or not version.strip():
        return payload

    if version == "2.0":
        return payload
    if version == "2.1":
        return _adapt_v2_1(payload)
    return payload


def _adapt_v2_1(payload: dict[str, Any]) -> dict[str, Any]:
    # v2.1 alternate shape supports a consolidated `stores` object.
    stores = payload.get("stores", {})
    if not isinstance(stores, dict):
        return payload

    out = dict(payload)
    out["tickets"] = {"queues": _ensure_list(stores.get("queues"))}
    out["projects"] = {"projects": _ensure_list(stores.get("projects"))}
    out["dashboard"] = {"dashboards": _ensure_list(stores.get("dashboards"))}
    out["kpi"] = {"kpis": _ensure_list(stores.get("kpis"))}
    out["hr_hub"] = {
        "employees": _ensure_list(stores.get("employees")),
        "request_types": _ensure_list(stores.get("request_types")),
    }
    return out


def _ensure_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []
