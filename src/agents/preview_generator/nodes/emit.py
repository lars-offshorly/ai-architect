from __future__ import annotations

from core.logging import get_logger

from ..bundles.registry import ALL_FEATURE_FLAGS
from ..state import PreviewGeneratorState

logger = get_logger(__name__)

# Map from flag name → display module name (for the modules[] list)
# Only core module-level flags are mapped; nav and notification flags are skipped.
_FLAG_TO_MODULE: dict[str, str] = {
    "projects-module":     "Projects",
    "tickets-module":      "Tickets",
    "hrhub-module":        "HRHub",
    "weaves-module":       "Weaves",
    "dashboard-module":    "Dashboard",
    "kpi-module":          "KPI",
    "calendar_module":     "Calendar",
    "chat-module":         "Chat",
    "ai-toolkit-module":   "AIToolkit",
    "rewards-module":      "Rewards",
}


def _build_flag_list(feature_flags: dict[str, bool]) -> list[dict]:
    """Reconstruct the full feature flags array in api-mocks format.

    Preserves id and module from ALL_FEATURE_FLAGS; sets isEnabled
    from the resolved dict.
    """
    result = []
    for entry in ALL_FEATURE_FLAGS:
        name = entry["name"]
        result.append({
            "id":          entry["id"],
            "name":        name,
            "description": entry["description"],
            "isEnabled":   feature_flags.get(name, False),
            "module":      entry["module"],
        })
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
    "project_mgmt": {"primary": "tasks",    "secondary": "milestones", "weaves": None},
    "hr_hub":       {"primary": "tickets",  "secondary": "queues",     "weaves": None},
    "ticketing":    {"primary": "tickets",  "secondary": "queues",     "weaves": None},
    "weaves":       {"primary": None,       "secondary": None,         "weaves": "weaves"},
}
_STORE_SCHEMA_FALLBACK: dict[str, str | None] = {
    "primary": "items", "secondary": "projects", "weaves": None,
}


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
    flag_list = _build_flag_list(state.feature_flags)
    modules   = _derive_modules(state.feature_flags)

    company_name = (
        state.user_context.company_name
        if state.user_context and state.user_context.company_name
        else None
    )

    # resolved_bundle_ids[0] is the registry key (already translated from catalog key)
    registry_key = state.resolved_bundle_ids[0] if state.resolved_bundle_ids else state.bundle_key

    generation_json: dict = {
        "schema_version": "1.0",
        "bundle_key":     state.bundle_key,
        "feature_flags":  flag_list,
        "modules":        modules,
        "config": {
            "permission_services": state.permission_services,
            "landing_pages":       state.landing_pages,
        },
    }

    dummy_data_json: dict = {
        "bundle_key":   state.bundle_key,
        "session_id":   state.session_id,
        "company_name": company_name,
        "stores":       _build_stores(registry_key, state),
    }

    logger.info(
        "session=%s — emitted preview: modules=%s flags_enabled=%d employees=%d",
        state.session_id,
        modules,
        sum(1 for f in flag_list if f["isEnabled"]),
        len(state.sample_employees),
    )

    return {"output": {"generation_json": generation_json, "dummy_data_json": dummy_data_json}}
