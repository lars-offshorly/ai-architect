"""Pipeline node: emits v2 preview output."""

from __future__ import annotations

from datetime import datetime, timezone

from core.logging import get_logger

from ..schemas import (
    CatalogRef,
    DashboardSection,
    EmployeeRecord,
    HrHubSection,
    KpiSection,
    ProjectsSection,
    TenantInfo,
    TenantProvisioningManifest,
    TicketQueuesSection,
)
from ..state import PreviewGeneratorState

logger = get_logger(__name__)

_FLAG_TO_MODULE: dict[str, str] = {
    "projects-module": "Project Management",
    "tickets-module": "Ticketing Tool",
    "hrhub-module": "HR Management",
    "weaves-module": "Weaves",
    "dashboard-module": "Dashboard",
    "kpi-module": "KPI",
    "calendar_module": "Calendar",
    "chat-module": "Chat",
    "ai-toolkit-module": "AI Toolkit",
    "rewards-module": "Rewards Store",
}


def _derive_modules(
    feature_flags: dict[str, bool], state: PreviewGeneratorState
) -> list[str]:
    modules: list[str] = []
    for flag_name, module_name in _FLAG_TO_MODULE.items():
        if feature_flags.get(flag_name, False) and module_name not in modules:
            modules.append(module_name)

    if state.catalog:
        bundle = state.catalog.get(state.bundle_key)
        if bundle and bundle.display_name not in modules:
            modules.insert(0, bundle.display_name)
    return modules


def _to_catalog_refs(items: list[dict]) -> list[CatalogRef]:
    refs: list[CatalogRef] = []
    for item in items:
        item_id = item.get("id")
        name = item.get("name")
        if isinstance(item_id, int) and item_id > 0 and isinstance(name, str) and name:
            refs.append(CatalogRef(id=item_id, name=name))
    return refs


def _to_employee_records(items: list[dict]) -> list[EmployeeRecord]:
    records: list[EmployeeRecord] = []
    for item in items:
        item_id = item.get("id")
        if not isinstance(item_id, int) or item_id <= 0:
            continue
        records.append(
            EmployeeRecord(
                id=item_id,
                position=str(item.get("position") or ""),
                team=str(item.get("team") or ""),
                department=str(item.get("department") or ""),
                job_title=str(item.get("job_title") or ""),
                job_type=str(item.get("job_type") or ""),
                job_level=str(item.get("job_level") or ""),
            )
        )
    return records


def build_manifest(state: PreviewGeneratorState) -> dict:
    now_utc = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    tenant = TenantInfo(
        company_name=(
            state.user_context.company_name
            if state.user_context and state.user_context.company_name
            else "Generated Tenant"
        ),
        industry=state.bundle_key,
        size_band=(
            state.user_context.company_size
            if state.user_context and state.user_context.company_size
            else "unknown"
        ),
        primary_region="unknown",
        locale="en-US",
        timezone="UTC",
    )
    manifest = TenantProvisioningManifest(
        schema_version="2.0",
        session_id=state.session_id,
        generated_at=now_utc,
        tenant=tenant,
        tickets=TicketQueuesSection(queues=_to_catalog_refs(state.sample_tickets)),
        projects=ProjectsSection(projects=_to_catalog_refs(state.sample_projects)),
        dashboard=DashboardSection(dashboards=[]),
        kpi=KpiSection(
            kpis=[
                CatalogRef(id=index + 1, name=metric.label)
                for index, metric in enumerate(state.kpi_metrics)
            ]
        ),
        hr_hub=HrHubSection(
            employees=_to_employee_records(state.sample_employees),
            request_types=[],
        ),
    )
    return manifest.model_dump()


def emit_preview(state: PreviewGeneratorState) -> dict:
    modules = _derive_modules(state.feature_flags, state)
    manifest = build_manifest(state)
    logger.info("session=%s — emitted v2 preview: modules=%s", state.session_id, modules)
    return {"output": {"modules": modules, "manifest": manifest}}
