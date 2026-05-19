"""Adapter: synthesize a v2 tenant-provisioning manifest from a v1 preview payload.

The full v2 pipeline (TenantProvisioningService + industry catalogs) is not yet
wired into the preview flow. This adapter projects what PreviewFlow already
produces — session signals plus ``dummy_data_json.stores`` — into the v2 shape
documented in ``new_json_samples/tenant_provisioning_bpo.jsonc``.

It is intentionally tolerant: any missing v1 store is filled with reasonable
defaults so the FE always has something to render. When the real selector +
emitter pipeline is wired in, this adapter can be deleted in favor of the
authoritative path.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from langchain_openai import ChatOpenAI

from agents.tenant_provisioning.catalog_view import CatalogView
from agents.tenant_provisioning.emitter import emit_tenant_provisioning
from agents.tenant_provisioning.selector import BaselineSelector, LLMSelector
from domain.models.session import Session
from domain.services.registry_facade import RegistryFacade

_DEFAULT_REQUEST_TYPES: list[dict[str, Any]] = [
    {"id": 801, "name": "Leave Request"},
    {"id": 802, "name": "Shift Swap"},
    {"id": 805, "name": "Equipment Request"},
]

_DEFAULT_EMPLOYEE: dict[str, Any] = {
    "id": 1,
    "position": "Operations Lead",
    "team": "Operations Team",
    "department": "Operations",
    "job_title": "Operations Lead",
    "job_type": "Full-Time",
    "job_level": "Manager",
}

_PH_REGION_PROFILE: tuple[str, str, str] = ("APAC", "en-PH", "Asia/Manila")
_DEFAULT_REGION_PROFILE: tuple[str, str, str] = ("APAC", "en-US", "UTC")


def _title_case(value: str) -> str:
    return " ".join(part.capitalize() for part in value.replace("_", " ").split())


def _infer_size_band(extraction: Any) -> str:
    if extraction is None:
        return "1-50"
    ps = getattr(extraction, "personalization_signals", None)
    if ps is None:
        return "1-50"
    headcount = len(getattr(ps, "employee_names", []) or [])
    if headcount >= 500:
        return "500+"
    if headcount >= 200:
        return "200-500"
    if headcount >= 50:
        return "50-200"
    return "1-50"


def _infer_level(role: str) -> str:
    r = role.lower()
    if any(k in r for k in ("director", "vp", "head of", "chief")):
        return "Director"
    if any(k in r for k in ("manager", "supervisor", "lead")):
        return "Manager"
    return "Staff"


def _queues_from_stores(stores: dict[str, Any]) -> list[dict[str, Any]]:
    raw_queues = stores.get("queues") or []
    if raw_queues:
        return [
            {
                "id": _coerce_int(q.get("id"), default=101 + idx),
                "name": str(q.get("name") or f"Queue {idx + 1}"),
            }
            for idx, q in enumerate(raw_queues)
            if isinstance(q, dict)
        ]

    tickets = stores.get("tickets") or []
    seen_cats: list[str] = []
    for t in tickets:
        if not isinstance(t, dict):
            continue
        cat = t.get("category") or t.get("queue") or t.get("department")
        if cat and cat not in seen_cats:
            seen_cats.append(cat)
    if seen_cats:
        return [
            {"id": 101 + idx, "name": f"{_title_case(cat)} Queue"}
            for idx, cat in enumerate(seen_cats)
        ]
    if tickets:
        return [{"id": 101, "name": "General Support Queue"}]
    return []


def _projects_from_stores(stores: dict[str, Any]) -> list[dict[str, Any]]:
    raw = stores.get("projects") or []
    if raw:
        return [
            {
                "id": _coerce_int(p.get("id"), default=501 + idx),
                "name": str(p.get("title") or p.get("name") or f"Project {idx + 1}"),
            }
            for idx, p in enumerate(raw)
            if isinstance(p, dict)
        ]

    seen: list[str] = []
    for t in stores.get("tasks") or []:
        if not isinstance(t, dict):
            continue
        proj = t.get("project")
        if proj and proj not in seen:
            seen.append(str(proj))
    return [{"id": 501 + idx, "name": p} for idx, p in enumerate(seen)]


def _dashboards_from_stores(stores: dict[str, Any]) -> list[dict[str, Any]]:
    widgets = stores.get("dashboard_widgets") or []
    seen_titles: list[str] = []
    for w in widgets:
        if not isinstance(w, dict):
            continue
        title = w.get("title")
        if title and title not in seen_titles:
            seen_titles.append(str(title))
    if seen_titles:
        return [
            {"id": 701 + idx, "name": title}
            for idx, title in enumerate(seen_titles[:6])
        ]
    if widgets:
        return [{"id": 701, "name": "Operations Overview"}]
    return [{"id": 701, "name": "Operations Overview"}]


def _kpis_from_stores(stores: dict[str, Any]) -> list[dict[str, Any]]:
    raw = stores.get("kpis") or []
    return [
        {
            "id": _coerce_int(k.get("id"), default=idx + 1),
            "name": str(k.get("label") or k.get("name") or f"KPI {idx + 1}"),
        }
        for idx, k in enumerate(raw)
        if isinstance(k, dict)
    ]


def _employees_from_signals(
    stores: dict[str, Any], extraction: Any
) -> list[dict[str, Any]]:
    raw = stores.get("employees") or []
    if raw:
        result: list[dict[str, Any]] = []
        for idx, emp in enumerate(raw):
            if not isinstance(emp, dict):
                continue
            title = (
                emp.get("job_title")
                or emp.get("role")
                or emp.get("position")
                or "Staff"
            )
            result.append(
                {
                    "id": _coerce_int(emp.get("id"), default=idx + 1),
                    "position": emp.get("position") or title,
                    "team": emp.get("team")
                    or emp.get("department")
                    or "Operations Team",
                    "department": emp.get("department") or "Operations",
                    "job_title": title,
                    "job_type": emp.get("job_type") or "Full-Time",
                    "job_level": emp.get("job_level") or _infer_level(title),
                }
            )
        if result:
            return result

    if extraction is None:
        return [dict(_DEFAULT_EMPLOYEE)]
    ps = getattr(extraction, "personalization_signals", None)
    if ps is None:
        return [dict(_DEFAULT_EMPLOYEE)]
    roles = list(getattr(ps, "role_names", []) or [])
    depts = list(getattr(ps, "department_names", []) or []) or ["Operations"]
    if not roles:
        return [dict(_DEFAULT_EMPLOYEE)]

    employees: list[dict[str, Any]] = []
    for idx, role in enumerate(roles[:8]):
        dept = depts[idx % len(depts)]
        employees.append(
            {
                "id": idx + 1,
                "position": role,
                "team": f"{dept} Team",
                "department": dept,
                "job_title": role,
                "job_type": "Full-Time",
                "job_level": _infer_level(role),
            }
        )
    return employees


def _request_types_from_stores(stores: dict[str, Any]) -> list[dict[str, Any]]:
    tickets = stores.get("tickets") or []
    seen: list[str] = []
    for t in tickets:
        if not isinstance(t, dict):
            continue
        cat = t.get("category")
        if cat and cat not in seen:
            seen.append(str(cat))
    if seen:
        return [
            {"id": 801 + idx, "name": f"{_title_case(cat)} Request"}
            for idx, cat in enumerate(seen)
        ]
    return [dict(item) for item in _DEFAULT_REQUEST_TYPES]


def _coerce_int(value: Any, default: int) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return default


def _conversation_text(history: list[dict[str, str]] | None) -> str:
    if not history:
        return ""
    return "\n".join(str(item.get("content") or "") for item in history)


def _infer_region_profile(text: str) -> tuple[str, str, str]:
    lowered = text.lower()
    if any(
        token in lowered
        for token in (
            " philippines",
            " philippine",
            " from ph",
            " based in ph",
            "manila",
            "cebu",
            "davao",
        )
    ):
        return _PH_REGION_PROFILE
    return _DEFAULT_REGION_PROFILE


def _extract_self_name(text: str) -> str | None:
    name_clause = r"([a-z][a-z' -]{1,60}?)"
    trailing_clause = r"(?=\s+(?:and|from|based|working)\b|[.,!?;:]|$)"
    patterns = (
        rf"\bmy name is\s+{name_clause}{trailing_clause}",
        rf"\bi am\s+{name_clause}{trailing_clause}",
        rf"\bi'm\s+{name_clause}{trailing_clause}",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        name = match.group(1).strip(" .,!?:;")
        # Keep short human names; avoid swallowing long trailing clauses.
        parts = [p for p in name.split() if p]
        if 1 <= len(parts) <= 3:
            return " ".join(part.capitalize() for part in parts)
    return None


async def build_v2_manifest(
    *,
    session: Session,
    dummy_data_json: dict[str, Any],
    bundle_key: str,
    display_name: str | None,
    conversation_history: list[dict[str, str]] | None = None,
    registry_facade: RegistryFacade | None = None,
    model: ChatOpenAI | None = None,
    disable_llm_calls: bool = False,
) -> dict[str, Any]:
    # pylint: disable=too-many-locals
    """Project a v1 PreviewFlow payload into the v2 tenant-provisioning shape.

    The returned dict matches the schema documented in
    ``new_json_samples/tenant_provisioning_bpo.jsonc`` (schema_version 2.0).
    """
    # Canonical v2 path: manifest + selector -> emitter.
    if registry_facade is not None:
        manifest = registry_facade.get_raw_manifest(bundle_key)
        if manifest is not None:
            catalog_view = CatalogView.from_manifest(manifest)
            user_message = _conversation_text(conversation_history)
            if disable_llm_calls or model is None:
                baseline_selector = BaselineSelector()
                selection = baseline_selector.select(catalog_view, user_message)
            else:
                llm_selector = LLMSelector(
                    model=model,
                    fallback_selector=BaselineSelector(),
                )
                selection = await llm_selector.select_async(catalog_view, user_message)
            return emit_tenant_provisioning(
                manifest,
                selection,
                session_id=session.session_id,
            )

    # Legacy tolerant synthesis fallback (kept for compatibility paths only).
    stores = (
        dummy_data_json.get("stores", {}) if isinstance(dummy_data_json, dict) else {}
    )

    extraction = session.accumulated_extraction
    ps = getattr(extraction, "personalization_signals", None) if extraction else None
    cs = getattr(extraction, "classification_signals", None) if extraction else None
    convo_text = _conversation_text(conversation_history)
    self_name = _extract_self_name(convo_text)
    primary_region, locale, tenant_timezone = _infer_region_profile(convo_text)
    if ps is not None:
        branch_blob = " ".join(getattr(ps, "branch_names", []) or [])
        if branch_blob:
            primary_region, locale, tenant_timezone = _infer_region_profile(branch_blob)

    company_name = (
        (getattr(ps, "company_name", None) if ps else None)
        or (f"{self_name}'s Workspace" if self_name else None)
        or display_name
        or _title_case(bundle_key)
        or "New Workspace"
    )
    industry = (
        ((getattr(cs, "domain_hints", []) or [None])[0] if cs else None)
        or bundle_key
        or "generic"
    )

    generated_at = datetime.now(timezone.utc).isoformat()
    if generated_at.endswith("+00:00"):
        generated_at = generated_at[:-6] + "Z"

    return {
        "schema_version": "2.0",
        "session_id": session.session_id,
        "generated_at": generated_at,
        "tenant": {
            "company_name": company_name,
            "industry": industry,
            "size_band": _infer_size_band(extraction),
            "primary_region": primary_region,
            "locale": locale,
            "timezone": tenant_timezone,
        },
        "tickets": {"queues": _queues_from_stores(stores)},
        "projects": {"projects": _projects_from_stores(stores)},
        "dashboard": {"dashboards": _dashboards_from_stores(stores)},
        "kpi": {"kpis": _kpis_from_stores(stores)},
        "hr_hub": {
            "employees": _employees_from_signals(stores, extraction),
            "request_types": _request_types_from_stores(stores),
        },
    }
