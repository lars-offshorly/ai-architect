"""Edit sub-graph node: parses natural-language instructions into EditActions.

Phase 1 (MVP): keyword-based parser.
Phase 2: LLM-based parser (keyword logic becomes fallback).
"""

from __future__ import annotations

import re

from core.logging import get_logger

from ..bundles.registry import METRICS_CATALOG
from ..schemas import EditAction, EditActionType

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Action verb detection
# ---------------------------------------------------------------------------

_ADD_VERBS = frozenset(["add", "enable", "include", "show", "turn on", "activate"])
_REMOVE_VERBS = frozenset(["remove", "disable", "hide", "drop", "turn off", "delete", "deactivate"])

# ---------------------------------------------------------------------------
# Module alias → flag name mapping
# ---------------------------------------------------------------------------

_MODULE_ALIASES: dict[str, str] = {
    "chat": "chat-module",
    "projects": "projects-module",
    "project": "projects-module",
    "tickets": "tickets-module",
    "ticket": "tickets-module",
    "ticketing": "tickets-module",
    "hr hub": "hrhub-module",
    "hrhub": "hrhub-module",
    "hr": "hrhub-module",
    "human resources": "hrhub-module",
    "weaves": "weaves-module",
    "weave": "weaves-module",
    "calendar": "calendar_module",
    "dashboard": "dashboard-module",
    "kpi": "kpi-module",
    "ai toolkit": "ai-toolkit-module",
    "ai-toolkit": "ai-toolkit-module",
    "smart vault": "ai-toolkit-module",
    "rewards": "rewards-module",
}

# Flag name → display module name (used to determine category)
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

# KPI label → slug mapping (built from METRICS_CATALOG)
_KPI_LABEL_TO_SLUG: dict[str, str] = {}
for _slug, _entry in METRICS_CATALOG.items():
    _KPI_LABEL_TO_SLUG[_entry["label"].lower()] = _slug
    # Also register the slug itself (with underscores replaced by spaces)
    _KPI_LABEL_TO_SLUG[_slug.replace("_", " ")] = _slug

# Dashboard-specific keywords
_DASHBOARD_KEYWORDS = frozenset(["dashboard", "dashboard widget", "dashboard module"])

# KPI-specific trigger words (used to distinguish "add kpi" from "add kpi module")
_KPI_TRIGGER_WORDS = frozenset(["kpi", "metric", "metrics", "indicator"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _detect_verb(text: str) -> str | None:
    """Return 'add' or 'remove' based on the first verb found, or None."""
    # Check multi-word verbs first
    for verb in ("turn on", "turn off"):
        if verb in text:
            return "add" if verb == "turn on" else "remove"

    # Single-word verbs
    words = text.split()
    for word in words:
        if word in _ADD_VERBS:
            return "add"
        if word in _REMOVE_VERBS:
            return "remove"
    return None


def _find_kpi_target(text: str) -> str | None:
    """Try to match a KPI slug or label in the text.

    Returns the slug if found, None otherwise.
    """
    # Direct slug match (e.g. "attendance_rate", "sla_compliance")
    for slug in METRICS_CATALOG:
        if slug in text:
            return slug

    # Label match (e.g. "SLA Compliance", "On-time Delivery Rate")
    # Normalize: lowercase, remove hyphens
    normalized = text.replace("-", " ")
    for label, slug in _KPI_LABEL_TO_SLUG.items():
        if label in normalized:
            return slug

    return None


def _find_module_target(text: str) -> str | None:
    """Try to match a module alias in the text.

    Checks longer aliases first to avoid partial matching issues
    (e.g. "hr hub" before "hr").
    """
    # Sort aliases by length (longest first) for greedy matching
    sorted_aliases = sorted(_MODULE_ALIASES.keys(), key=len, reverse=True)
    for alias in sorted_aliases:
        if alias in text:
            return _MODULE_ALIASES[alias]
    return None


def _is_kpi_context(text: str) -> bool:
    """Check if the instruction is explicitly about a KPI/metric, not a module."""
    return any(word in text for word in _KPI_TRIGGER_WORDS)


def _is_dashboard_only(text: str) -> bool:
    """Check if the instruction is about the dashboard itself (not a module add/remove)."""
    # "remove dashboard" with no other module reference means dashboard action
    return "dashboard" in text and not any(
        alias in text
        for alias in _MODULE_ALIASES
        if alias != "dashboard"
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_edit_instruction(instruction: str) -> EditAction:
    """Parse a natural-language edit instruction into an EditAction.

    Phase 1 (MVP): keyword-based parsing.
    Handles: add/remove module, add/remove KPI, add/remove dashboard.
    Falls back to 'unsupported' for unrecognised instructions.
    """
    raw = instruction
    text = instruction.lower().strip()

    if not text:
        return EditAction(
            action_type=EditActionType.unsupported,
            raw_instruction=raw,
        )

    verb = _detect_verb(text)
    if verb is None:
        logger.info("No action verb detected in: %r", raw)
        return EditAction(
            action_type=EditActionType.unsupported,
            raw_instruction=raw,
        )

    # --- KPI detection (check before module to handle "remove attendance KPI") ---
    kpi_target = _find_kpi_target(text)
    if kpi_target and _is_kpi_context(text):
        action_type = EditActionType.add_kpi if verb == "add" else EditActionType.remove_kpi
        logger.info("Parsed %s KPI: %r → %s", verb, raw, kpi_target)
        return EditAction(
            action_type=action_type,
            target=kpi_target,
            raw_instruction=raw,
        )

    # --- Dashboard detection ---
    if _is_dashboard_only(text):
        action_type = EditActionType.add_dashboard if verb == "add" else EditActionType.remove_dashboard
        logger.info("Parsed %s dashboard: %r", verb, raw)
        return EditAction(
            action_type=action_type,
            target="dashboard-module",
            raw_instruction=raw,
        )

    # --- Module detection ---
    module_target = _find_module_target(text)
    if module_target:
        action_type = EditActionType.add_module if verb == "add" else EditActionType.remove_module
        logger.info("Parsed %s module: %r → %s", verb, raw, module_target)
        return EditAction(
            action_type=action_type,
            target=module_target,
            raw_instruction=raw,
        )

    # --- KPI fallback: verb + slug without explicit "kpi"/"metric" word ---
    if kpi_target:
        action_type = EditActionType.add_kpi if verb == "add" else EditActionType.remove_kpi
        logger.info("Parsed %s KPI (fallback): %r → %s", verb, raw, kpi_target)
        return EditAction(
            action_type=action_type,
            target=kpi_target,
            raw_instruction=raw,
        )

    logger.info("No recognised target in: %r (verb=%s)", raw, verb)
    return EditAction(
        action_type=EditActionType.unsupported,
        raw_instruction=raw,
    )
