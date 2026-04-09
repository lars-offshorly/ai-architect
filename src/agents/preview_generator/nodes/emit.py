"""Pipeline node: assembles the final PreviewOutput from resolved state."""

from __future__ import annotations

from core.logging import get_logger

from ..schemas import DummyDataJson, GenerationJson, PreviewOutput
from ..state import PreviewGeneratorState

logger = get_logger(__name__)

# Map from flag name → display module name (for the modules[] list)
# Only core module-level flags are mapped; nav and notification flags are skipped.
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


def _build_flag_list(
    feature_flags: dict[str, bool], state: PreviewGeneratorState
) -> list[dict]:
    """Reconstruct the full feature flags array in api-mocks format.

    Preserves id and module from canonical catalog; sets isEnabled
    from the resolved dict in state.
    """
    if state.catalog is None:
        return []

    result = []
    for entry in state.catalog.get_feature_flags():
        name = entry["name"]
        result.append(
            {
                "id": entry["id"],
                "name": name,
                "description": entry["description"],
                "isEnabled": feature_flags.get(name, False),
                "module": entry["module"],
            }
        )
    return result


def _derive_modules(feature_flags: dict[str, bool]) -> list[str]:
    """Derive active module display names from enabled flags."""
    modules: list[str] = []
    for flag_name, module_name in _FLAG_TO_MODULE.items():
        if feature_flags.get(flag_name, False) and module_name not in modules:
            modules.append(module_name)
    return modules


# Store name mapping per registry bundle key.
# Keyed by the registry key (post-translation); maps internal state fields
# to the frontend store names defined in the dummy_data.json templates.
# "primary"   → sample_tickets  (main work items: tickets / tasks)
# "secondary" → sample_projects (groupings: queues / milestones)
# "weaves"    → sample_weaves   (only included for weaves-enabled bundles)
_STORE_SCHEMA: dict[str, dict[str, str | None]] = {
    "project_mgmt": {"primary": "tasks", "secondary": "milestones", "weaves": None},
    "hr_management": {"primary": "tickets", "secondary": "queues", "weaves": None},
    "ticketing": {"primary": "tickets", "secondary": "queues", "weaves": None},
    "weaves": {"primary": None, "secondary": None, "weaves": "weaves"},
}
_STORE_SCHEMA_FALLBACK: dict[str, str | None] = {
    "primary": "items",
    "secondary": "projects",
    "weaves": None,
}


_BUNDLE_CONFIG_FIELDS: dict[str, list[str]] = {
    "hr_management": [
        "ticket_categories",
        "default_statuses",
        "default_priorities",
        "queue_names",
        "kpi_definitions",
    ],
    "project_mgmt": [
        "task_statuses",
        "task_priorities",
        "milestone_statuses",
        "kpi_definitions",
    ],
    "ticketing": [
        "work_order_statuses",
        "work_order_priorities",
        "service_types",
        "kpi_definitions",
    ],
}
_BUNDLE_CONFIG_FALLBACK_FIELDS: list[str] = [
    "ticket_statuses",
    "ticket_priorities",
    "kpi_definitions",
]


def _build_config(
    registry_key: str,
    permission_services: list[str],
    landing_pages: list[dict],
    kpi_metrics: list,
    sample_tickets: list[dict],
    sample_employees: list[dict],
) -> dict[str, object]:
    """Build the per-bundle config dict for generation_json."""
    config: dict[str, object] = {
        "permission_services": permission_services,
        "landing_pages": landing_pages,
    }

    # Derive sample values from already-generated data
    ticket_statuses = list(
        dict.fromkeys(t.get("status", "") for t in sample_tickets if t.get("status"))
    )
    ticket_types = list(
        dict.fromkeys(t.get("type", "") for t in sample_tickets if t.get("type"))
    )
    ticket_priorities = list(
        dict.fromkeys(
            t.get("priority", "") for t in sample_tickets if t.get("priority")
        )
    )
    dept_names = list(
        dict.fromkeys(
            e.get("department", "") for e in sample_employees if e.get("department")
        )
    )

    fields = _BUNDLE_CONFIG_FIELDS.get(registry_key, _BUNDLE_CONFIG_FALLBACK_FIELDS)

    _field_values: dict[str, object] = {
        "kpi_definitions": [
            {"key": k.key, "label": k.label, "unit": k.type}
            for k in kpi_metrics
        ],
        # ticketing bundle
        "service_types": ticket_types,
        "work_order_statuses": ticket_statuses,
        "work_order_priorities": ticket_priorities,
        # hr_hub bundle
        "ticket_categories": ticket_types,
        "default_statuses": ticket_statuses,
        "default_priorities": ticket_priorities,
        "queue_names": dept_names,
        # project_mgmt bundle
        "task_statuses": ticket_statuses,
        "task_priorities": ticket_priorities,
        "milestone_statuses": ["Planning", "In Progress", "Completed", "On Hold"],
        # generic fallback fields
        "ticket_statuses": ticket_statuses,
        "ticket_priorities": ticket_priorities,
    }

    for field in fields:
        config[field] = _field_values.get(field, [])
    return config


def _build_stores(registry_key: str, state: PreviewGeneratorState) -> dict:
    """Build the stores dict with frontend-correct key names for this bundle."""
    schema = _STORE_SCHEMA.get(registry_key, _STORE_SCHEMA_FALLBACK)
    stores: dict = {"kpis": state.kpi_metrics, "dashboard_widgets": []}
    if schema["primary"]:
        stores[schema["primary"]] = state.sample_tickets
    if schema["secondary"]:
        stores[schema["secondary"]] = state.sample_projects
    if schema["weaves"]:
        stores[schema["weaves"]] = state.sample_weaves
    return stores


def emit_preview(state: PreviewGeneratorState) -> dict:
    """Assemble the two output payloads consumed by AppPayload.

    generation_json — Knit workspace configuration:
      schema_version, bundle_key, feature_flags (full list with isEnabled),
      modules (active module names), config.permission_services,
      config.landing_pages

    dummy_data_json — sample data stores:
      bundle_key, session_id, company_name,
      stores — keys match the frontend dummy_data.json template per bundle

    Both are placed in state.output so service.py can unpack them.
    """
    flag_list = _build_flag_list(state.feature_flags, state)
    modules = _derive_modules(state.feature_flags)

    company_name = (
        state.user_context.company_name
        if state.user_context and state.user_context.company_name
        else None
    )

    # Use render_key for AD-2 mapped bundles that define preview flags.
    # Bundles without flag metadata (e.g. finance) should keep bundle_key so
    # they naturally fall back to generic store/config schema.
    registry_key = state.bundle_key
    if state.catalog is not None:
        bundle = state.catalog.get(state.bundle_key)
        if bundle is not None and bundle.render_key and bundle.flags:
            registry_key = bundle.render_key
    elif state.resolved_bundle_ids:
        registry_key = state.resolved_bundle_ids[0]

    generation_json = GenerationJson(
        schema_version="1.0",
        bundle_key=state.bundle_key,
        feature_flags=flag_list,
        modules=modules,
        config=_build_config(
            registry_key,
            state.permission_services,
            state.landing_pages,
            state.kpi_metrics,
            state.sample_tickets,
            state.sample_employees,
        ),
    )

    stores = _build_stores(registry_key, state)

    dummy_data_json = DummyDataJson(
        bundle_key=state.bundle_key,
        session_id=state.session_id,
        company_name=company_name,
        stores=stores,
    )

    logger.info(
        "session=%s — emitted preview: modules=%s flags_enabled=%d stores=%s",
        state.session_id,
        modules,
        sum(1 for f in flag_list if f["isEnabled"]),
        list(stores.keys()),
    )

    return {
        "output": PreviewOutput(
            generation_json=generation_json, dummy_data_json=dummy_data_json
        ).model_dump()
    }
