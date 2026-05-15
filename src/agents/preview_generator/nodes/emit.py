"""Pipeline node: assembles the final PreviewOutput from resolved state."""

from __future__ import annotations

from datetime import datetime, timezone

from core.logging import get_logger

from ..dashboard.static_ids import BUNDLE_TO_DASHBOARD, DASHBOARD_IDS, WIDGET_TEMPLATES
from ..schemas import DummyDataJson, GenerationJson, PreviewOutput
from ..state import PreviewGeneratorState

logger = get_logger(__name__)

_DEFAULT_DASHBOARD_NAME = "Tickets Dashboard"

# Map from flag name → display module name (for the modules[] list)
# Only core module-level flags are mapped; nav and notification flags are skipped.
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


def _build_flag_list( #TODO: Remove, redundant 
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


def _derive_modules( #TODO: Remove, redundant 
    feature_flags: dict[str, bool], state: PreviewGeneratorState
) -> list[str]:
    """Derive active module display names from enabled flags."""
    modules: list[str] = []
    for flag_name, module_name in _FLAG_TO_MODULE.items():
        if feature_flags.get(flag_name, False) and module_name not in modules:
            modules.append(module_name)

    # For industry/standalone bundles, ensure the bundle name itself is a valid module
    if state.catalog:
        bundle = state.catalog.get(state.bundle_key)
        if bundle and bundle.display_name not in modules:
            # Insert at front as it's the primary hub for this bundle
            modules.insert(0, bundle.display_name)

    return modules


# Store name mapping per registry bundle key.
# Keyed by the registry key (post-translation); maps internal state fields
# to the frontend store names defined in the dummy_data.json templates.
# "primary"   → sample_tickets  (main work items: tickets / tasks)
# "secondary" → sample_projects (groupings: queues / milestones)
# "weaves"    → sample_weaves   (only included for weaves-enabled bundles)
_STORE_SCHEMA: dict[str, dict[str, str | None]] = {
    # Tier 1 — canonical registry keys
    "project_mgmt": {"primary": "tasks", "secondary": "milestones", "weaves": None},
    "hr_management": {"primary": "tickets", "secondary": "queues", "weaves": None},
    "hr_hub": {"primary": "tickets", "secondary": "queues", "weaves": None},
    "ticketing": {"primary": "tickets", "secondary": "queues", "weaves": None},
    "weaves": {"primary": None, "secondary": None, "weaves": "weaves"},
    # Tier 3 — industry bundles (project-centric)
    "construction": {"primary": "tasks", "secondary": "projects", "weaves": None},
    "real_estate": {"primary": "tasks", "secondary": "projects", "weaves": None},
    "finance": {"primary": "tasks", "secondary": "projects", "weaves": None},
    "marketing": {"primary": "tasks", "secondary": "projects", "weaves": None},
    "sales": {"primary": "tasks", "secondary": "projects", "weaves": None},
    "education": {"primary": "tasks", "secondary": "projects", "weaves": None},
    # Tier 3 — industry bundles (ticket-centric)
    "healthcare": {"primary": "tickets", "secondary": None, "weaves": None},
    "legal_services": {"primary": "tickets", "secondary": None, "weaves": None},
    "generic": {"primary": "tickets", "secondary": None, "weaves": None},
    # Tier 3 — mixed (has tickets + projects + tasks)
    "all_microservices": {
        "primary": "tickets",
        "secondary": "projects",
        "weaves": None,
    },
}

# Only these canonical tier-1 bundle keys should have their render_key applied
# for store/config schema derivation. Other bundles that share a render_key
# (e.g. sales -> project_mgmt) must not inherit the tier-1 schema.
_TIER1_CANONICAL_KEYS: frozenset[str] = frozenset(
    {"hr_management", "project_mgmt", "ticketing"}
)
_STORE_SCHEMA_FALLBACK: dict[str, str | None] = {
    "primary": "items",
    "secondary": "projects",
    "weaves": None,
}


_BUNDLE_CONFIG_FIELDS: dict[str, list[str]] = {
    "hr_hub": [
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

#TODO: Modify to match canonical contract
def _build_config(registry_key: str, state: PreviewGeneratorState) -> dict[str, object]:
    """Build the per-bundle config dict for generation_json."""
    config: dict[str, object] = {
        "permission_services": state.permission_services,
        "landing_pages": state.landing_pages,
    }

    # Derive sample values from already-generated data
    ticket_statuses = list(
        dict.fromkeys(
            t.get("status", "") for t in state.sample_tickets if t.get("status")
        )
    )
    ticket_types = list(
        dict.fromkeys(t.get("type", "") for t in state.sample_tickets if t.get("type"))
    )
    ticket_priorities = list(
        dict.fromkeys(
            t.get("priority", "") for t in state.sample_tickets if t.get("priority")
        )
    )
    dept_names = list(
        dict.fromkeys(
            e.get("department", "")
            for e in state.sample_employees
            if e.get("department")
        )
    )

    fields = _BUNDLE_CONFIG_FIELDS.get(registry_key, _BUNDLE_CONFIG_FALLBACK_FIELDS)

    _field_values: dict[str, object] = {
        "kpi_definitions": [
            {"key": k.key, "label": k.label, "unit": k.type} for k in state.kpi_metrics
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
    dashboard_widgets = _build_dashboard_widgets(state)
    dashboard_generation_output = _build_dashboard_generation_output(
        state, dashboard_widgets, schema
    )
    stores: dict = {
        "kpis": [
            {"id": i + 1, **m.model_dump()} for i, m in enumerate(state.kpi_metrics)
        ],
        "dashboard_widgets": dashboard_widgets,
        "dashboard_generation_output": dashboard_generation_output,
    }
    if schema["primary"]:
        stores[schema["primary"]] = state.sample_tickets
    if schema["secondary"]:
        stores[schema["secondary"]] = state.sample_projects
    if schema["weaves"]:
        stores[schema["weaves"]] = state.sample_weaves
    return stores


def _build_dashboard_widgets(
    state: PreviewGeneratorState,
) -> list[dict[str, object]]:
    """Return WIDGET_TEMPLATES entries for this bundle dashboard as fallback.

    Format matches the canonical static enrichment format:
    {"widget_template_external_id": int, "name": str}

    PreviewFlow._enrich_dashboard_widgets() replaces this with real static data on
    the success path, or clears it to [] on the failure path.
    """
    dash_name = BUNDLE_TO_DASHBOARD.get(state.bundle_key, _DEFAULT_DASHBOARD_NAME)
    dash_id = DASHBOARD_IDS.get(dash_name, DASHBOARD_IDS[_DEFAULT_DASHBOARD_NAME])
    return list(WIDGET_TEMPLATES.get(dash_id, []))


def _build_debug_widgets(
    state: PreviewGeneratorState,
    templates: list[dict[str, object]],
    primary_store: str,
) -> list[dict[str, object]]:
    """Build the debug widgets for the dashboard payload."""
    debug_widgets: list[dict[str, object]] = []
    if state.kpi_metrics:
        metric = state.kpi_metrics[0]
        w: dict[str, object] = {
            "type": "number",
            "name": metric.label,
            "value": str(metric.sample_value),
            "calculation": {
                "datasets": [
                    {
                        "module": state.bundle_key.replace("_", " ").title(),
                        "data_source": "kpis",
                    }
                ]
            },
        }
        if templates:
            w["widget_template_external_id"] = templates[0][
                "widget_template_external_id"
            ]
        debug_widgets.append(w)

    w_bar: dict[str, object] = {
        "type": "bar",
        "title": f"{primary_store.replace('_', ' ').title()} by Status",
        "data_config": {
            "module": state.bundle_key.replace("_", " ").title(),
            "data_source": primary_store,
            "group_by": ["status"],
            "aggregation": "count",
        },
    }
    if len(templates) > 1:
        w_bar["widget_template_external_id"] = templates[1][
            "widget_template_external_id"
        ]
    debug_widgets.append(w_bar)

    w_list: dict[str, object] = {
        "type": "list",
        "name": "KPI Detail List",
        "data_config": {"module": "KPI", "data_source": "kpis"},
        "column_count": 4,
        "column_width": 250,
    }
    if len(templates) > 2:
        w_list["widget_template_external_id"] = templates[2][
            "widget_template_external_id"
        ]
    debug_widgets.append(w_list)

    return debug_widgets


def _count_widget_types(widgets: list[dict[str, object]]) -> dict[str, int]:
    """Count the occurrences of each widget type."""
    type_counts: dict[str, int] = {
        "text": 0,
        "number": 0,
        "bar": 0,
        "hbar": 0,
        "pie": 0,
        "line": 0,
        "scatter": 0,
        "list": 0,
        "combo": 0,
        "embed": 0,
    }
    for widget in widgets:
        widget_type = widget.get("type")
        if isinstance(widget_type, str) and widget_type in type_counts:
            type_counts[widget_type] += 1
    type_counts["total"] = len(widgets)
    return type_counts


def _get_data_sources(state: PreviewGeneratorState, primary_store: str) -> list[str]:
    """Retrieve data sources used for the dashboard generation."""
    data_sources_set = {
        str(m.source_service)
        for m in state.kpi_metrics
        if isinstance(m.source_service, str) and m.source_service
    }
    data_sources = sorted(data_sources_set)
    if not data_sources:
        data_sources = ["kpis", primary_store]
    return data_sources


def _build_dashboard_generation_output(
    state: PreviewGeneratorState,
    dashboard_widgets: list[dict[str, object]],
    schema: dict[str, str | None],
) -> dict[str, object]:
    """Build OpenAPI-aligned dashboard generation response structure."""
    primary_store = str(schema.get("primary") or "items")
    report_length = sum(
        len(str(message.get("content", ""))) for message in state.conversation_history
    )

    dash_name = BUNDLE_TO_DASHBOARD.get(
        state.bundle_key, f"{state.bundle_key.replace('_', ' ').title()} Dashboard"
    )
    dash_id = DASHBOARD_IDS.get(dash_name, DASHBOARD_IDS[_DEFAULT_DASHBOARD_NAME])
    templates: list[dict[str, object]] = list(WIDGET_TEMPLATES.get(dash_id, []))

    debug_widgets = _build_debug_widgets(state, templates, primary_store)
    widget_count = _count_widget_types(debug_widgets)
    data_sources = _get_data_sources(state, primary_store)

    return {
        "success": True,
        "dashboard": {
            "id": f"dash-{state.session_id[:8]}",
            "external_id": dash_id,
            "name": dash_name,
            "url": None,
        },
        "widgets": widget_count,
        "execution_time": "0m 1s",
        "errors": [],
        "debug_payload": {
            "widgets": debug_widgets,
            "total_widgets": len(debug_widgets),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "widget_breakdown": widget_count,
        },
        "generation_metadata": {
            "report_length": report_length,
            "widgets_extracted": len(dashboard_widgets),
            "widgets_explicit": len(dashboard_widgets),
            "data_sources_used": data_sources,
            "processing_steps": [
                "extract_context",
                "resolve_feature_flags",
                "generate_sample_data",
                "build_kpis",
                "emit_preview",
            ],
        },
    }


def emit_preview(state: PreviewGeneratorState) -> dict: #TODO: Remove, redundant, we will only transition to app endpoint for final endpoint
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
    modules = _derive_modules(state.feature_flags, state)

    company_name = (
        state.user_context.company_name
        if state.user_context and state.user_context.company_name
        else None
    )

    # Use a render-compat key only for internal schema derivation.
    # Public/API bundle identity remains the canonical catalog bundle_key.
    registry_key = state.bundle_key
    if state.bundle_key in _TIER1_CANONICAL_KEYS and state.catalog is not None:
        bundle = state.catalog.get(state.bundle_key)
        if bundle is not None and bundle.render_key:
            registry_key = bundle.render_key

    generation_json = GenerationJson(
        schema_version="1.0",
        bundle_key=state.bundle_key,
        feature_flags=flag_list,
        modules=modules,
        config=_build_config(registry_key, state),
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
