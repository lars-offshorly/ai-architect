"""Edit sub-graph node: applies an EditAction to an existing preview payload.

State retention rule: only the targeted part of the JSON changes.
Everything else is preserved. Cascading effects are handled explicitly.
"""

from __future__ import annotations

import copy

from core.logging import get_logger

from ..bundles.registry import METRICS_CATALOG
from ..schemas import EditAction, EditActionType

logger = get_logger(__name__)


# Flag name → display module name (mirrors emit.py)
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

# Module flag → source_service and store keys that should be removed on cascade
_MODULE_CASCADE: dict[str, dict] = {
    "tickets-module": {
        "source_service": "tickets",
        "store_keys": ["tickets"],
    },
    "projects-module": {
        "source_service": "projects",
        "store_keys": ["tasks", "milestones", "projects"],
    },
    "hrhub-module": {
        "source_service": "hr_hub",
        "store_keys": ["employees"],
    },
    "weaves-module": {
        "source_service": "weaves",
        "store_keys": ["weaves"],
    },
    "chat-module": {
        "source_service": None,
        "store_keys": [],
    },
    "dashboard-module": {
        "source_service": None,
        "store_keys": ["dashboard_widgets"],
    },
    "kpi-module": {
        "source_service": None,
        "store_keys": [],
    },
    "calendar_module": {
        "source_service": None,
        "store_keys": [],
    },
    "ai-toolkit-module": {
        "source_service": None,
        "store_keys": [],
    },
    "rewards-module": {
        "source_service": None,
        "store_keys": [],
    },
}

# Sample values per metric type — same as kpi.py
_SAMPLE_VALUES: dict[str, float | int | str] = {
    "percentage": 87.5,
    "count": 42,
    "duration": 3.2,
    "status": "Healthy",
    "ratio": 0.72,
}


# ---------------------------------------------------------------------------
# Internal mutators (all operate on the deep-copied payload)
# ---------------------------------------------------------------------------


def _set_flag(flags: list[dict], flag_name: str, enabled: bool) -> None:
    """Set isEnabled for a specific flag in the feature_flags list."""
    for flag in flags:
        if flag["name"] == flag_name:
            flag["isEnabled"] = enabled
            return


def _remove_module(payload: dict, flag_name: str) -> str | None:
    """Remove a module: disable flag, remove from modules[], cascade."""
    gen = payload["generation_json"]
    dummy = payload["dummy_data_json"]

    # 1. Disable the flag
    _set_flag(gen["feature_flags"], flag_name, False)

    # 2. Remove display name from modules lists
    display_name = _FLAG_TO_MODULE.get(flag_name)
    if display_name:
        gen["modules"] = [m for m in gen["modules"] if m != display_name]
        payload["modules"] = [m for m in payload["modules"] if m != display_name]

    # 3. Cascade: remove related KPIs and stores
    cascade = _MODULE_CASCADE.get(flag_name, {})
    source_service = cascade.get("source_service")
    store_keys = cascade.get("store_keys", [])

    if source_service and "stores" in dummy:
        stores = dummy["stores"]
        if "kpis" in stores:
            stores["kpis"] = [
                k for k in stores["kpis"] if k.get("source_service") != source_service
            ]

    if "stores" in dummy:
        for key in store_keys:
            dummy["stores"].pop(key, None)

    logger.info("Removed module %s (display=%s)", flag_name, display_name)
    return None


def _add_module(payload: dict, flag_name: str) -> str | None:
    """Add a module: enable flag, add to modules[] (no data generation)."""
    gen = payload["generation_json"]

    # 1. Enable the flag
    _set_flag(gen["feature_flags"], flag_name, True)

    # 2. Add display name to modules lists (skip if already present)
    display_name = _FLAG_TO_MODULE.get(flag_name)
    if display_name:
        if display_name not in gen["modules"]:
            gen["modules"].append(display_name)
        if display_name not in payload["modules"]:
            payload["modules"].append(display_name)

    logger.info("Added module %s (display=%s)", flag_name, display_name)
    return None


def _remove_kpi(payload: dict, kpi_key: str) -> str | None:
    """Remove a KPI by slug from stores.kpis and config.kpi_definitions."""
    dummy = payload["dummy_data_json"]
    gen = payload["generation_json"]

    # Remove from stores
    if "stores" in dummy and "kpis" in dummy["stores"]:
        dummy["stores"]["kpis"] = [
            k for k in dummy["stores"]["kpis"] if k.get("key") != kpi_key
        ]

    # Remove from config.kpi_definitions
    config = gen.get("config", {})
    if "kpi_definitions" in config:
        config["kpi_definitions"] = [
            k for k in config["kpi_definitions"] if k != kpi_key
        ]

    logger.info("Removed KPI %s", kpi_key)
    return None


def _add_kpi(payload: dict, kpi_key: str) -> str | None:
    """Add a KPI by slug from METRICS_CATALOG to stores.kpis and config."""
    catalog_entry = METRICS_CATALOG.get(kpi_key)
    if catalog_entry is None:
        warning = f"KPI '{kpi_key}' not found in metrics catalog."
        logger.warning(warning)
        return warning

    dummy = payload["dummy_data_json"]
    gen = payload["generation_json"]

    # Add to stores.kpis (skip if already present)
    if "stores" not in dummy:
        dummy["stores"] = {}
    if "kpis" not in dummy["stores"]:
        dummy["stores"]["kpis"] = []

    existing_keys = {k.get("key") for k in dummy["stores"]["kpis"]}
    if kpi_key not in existing_keys:
        dummy["stores"]["kpis"].append(
            {
                "key": catalog_entry["key"],
                "label": catalog_entry["label"],
                "type": catalog_entry["type"],
                "source_service": catalog_entry["source_service"],
                "sample_value": _SAMPLE_VALUES.get(catalog_entry["type"], 0),
            }
        )

    # Add to config.kpi_definitions
    config = gen.get("config", {})
    if "kpi_definitions" not in config:
        config["kpi_definitions"] = []
    if kpi_key not in config["kpi_definitions"]:
        config["kpi_definitions"].append(kpi_key)
    gen["config"] = config

    logger.info("Added KPI %s", kpi_key)
    return None


def _remove_dashboard(payload: dict) -> str | None:
    """Remove dashboard: disable flag, remove module, clear widgets."""
    _set_flag(payload["generation_json"]["feature_flags"], "dashboard-module", False)

    gen = payload["generation_json"]
    gen["modules"] = [m for m in gen["modules"] if m != "Dashboard"]
    payload["modules"] = [m for m in payload["modules"] if m != "Dashboard"]

    dummy = payload["dummy_data_json"]
    if "stores" in dummy:
        dummy["stores"].pop("dashboard_widgets", None)

    logger.info("Removed dashboard")
    return None


def _add_dashboard(payload: dict) -> str | None:
    """Add dashboard: enable flag, add module."""
    _set_flag(payload["generation_json"]["feature_flags"], "dashboard-module", True)

    gen = payload["generation_json"]
    if "Dashboard" not in gen["modules"]:
        gen["modules"].append("Dashboard")
    if "Dashboard" not in payload["modules"]:
        payload["modules"].append("Dashboard")

    logger.info("Added dashboard")
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def apply_edit(
    payload: dict,
    action: EditAction,
) -> tuple[dict, str | None]:
    """Apply an EditAction to an existing preview payload.

    Returns (updated_payload, warning_or_None).
    The input payload is NOT mutated — a deep copy is made.

    Raises no exceptions; unsupported actions return the original with a warning.
    """
    # Deep copy to avoid mutating the caller's data
    result = copy.deepcopy(payload)
    warning: str | None = None

    if action.action_type == EditActionType.unsupported:
        warning = (
            f"Unsupported edit instruction: '{action.raw_instruction}'. "
            "No changes were applied."
        )
        result["warning"] = warning
        return result, warning

    target = action.target

    if action.action_type == EditActionType.remove_module and target:
        warning = _remove_module(result, target)
        return result, warning

    if action.action_type == EditActionType.add_module and target:
        warning = _add_module(result, target)
        return result, warning

    if action.action_type == EditActionType.remove_kpi and target:
        warning = _remove_kpi(result, target)
        return result, warning

    if action.action_type == EditActionType.add_kpi and target:
        warning = _add_kpi(result, target)
        return result, warning

    if action.action_type == EditActionType.remove_dashboard:
        warning = _remove_dashboard(result)
        return result, warning

    if action.action_type == EditActionType.add_dashboard:
        warning = _add_dashboard(result)
        return result, warning

    # Fallback — shouldn't reach here if EditActionType is exhaustive
    logger.warning("Unhandled action type: %s", action.action_type)
    return result, None
