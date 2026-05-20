"""Edit sub-graph node: parses natural language instructions into EditAction schemas.

Currently uses heuristic keyword matching.
Phase 2: replace with a lightweight LLM call or a better semantic parser.
"""

from __future__ import annotations

import re

from catalog.bundle_catalog import BundleCatalog
from core.logging import get_logger

from ..schemas import EditAction, EditActionType

logger = get_logger(__name__)

# Module labels → flag names (mirrors emit.py)
_MODULE_MAP: dict[str, str] = {
    "hr": "hrhub-module",
    "projects": "projects-module",
    "tickets": "tickets-module",
    "hr hub": "hrhub-module",
    "weaves": "weaves-module",
    "dashboard": "dashboard-module",
    "kpi": "kpi-module",
    "calendar": "calendar_module",
    "chat": "chat-module",
    "ai toolkit": "ai-toolkit-module",
    "smart vault": "ai-toolkit-module",
    "rewards": "rewards-module",
}

_ADD_VERBS = ("add", "enable", "show", "include")
_REMOVE_VERBS = ("remove", "delete", "hide", "disable", "drop")


def _has_any_verb(text: str, verbs: tuple[str, ...]) -> bool:
    return any(verb in text for verb in verbs)


def _dashboard_action(text: str, instruction: str) -> EditAction | None:
    if "dashboard" not in text:
        return None
    if _has_any_verb(text, _ADD_VERBS):
        return EditAction(
            action_type=EditActionType.ADD_DASHBOARD,
            target="dashboard-module",
            raw_instruction=instruction,
        )
    if _has_any_verb(text, _REMOVE_VERBS):
        return EditAction(
            action_type=EditActionType.REMOVE_DASHBOARD,
            target="dashboard-module",
            raw_instruction=instruction,
        )
    return None


def _kpi_label_to_slug(metrics_catalog: dict[str, dict[str, object]]) -> dict[str, str]:
    label_to_slug: dict[str, str] = {}
    for slug, entry in metrics_catalog.items():
        label = entry.get("label")
        if isinstance(label, str):
            label_to_slug[label.lower()] = slug
    return label_to_slug


def _kpi_action(
    text: str,
    instruction: str,
    metrics_catalog: dict[str, dict[str, object]],
) -> EditAction | None:
    for slug in metrics_catalog:
        if slug in text or slug.replace("_", " ") in text:
            if _has_any_verb(text, _ADD_VERBS):
                return EditAction(
                    action_type=EditActionType.ADD_KPI,
                    target=slug,
                    raw_instruction=instruction,
                )
            if _has_any_verb(text, _REMOVE_VERBS):
                return EditAction(
                    action_type=EditActionType.REMOVE_KPI,
                    target=slug,
                    raw_instruction=instruction,
                )

    for label, slug in _kpi_label_to_slug(metrics_catalog).items():
        if label in text:
            if _has_any_verb(text, _ADD_VERBS):
                return EditAction(
                    action_type=EditActionType.ADD_KPI,
                    target=slug,
                    raw_instruction=instruction,
                )
            if _has_any_verb(text, _REMOVE_VERBS):
                return EditAction(
                    action_type=EditActionType.REMOVE_KPI,
                    target=slug,
                    raw_instruction=instruction,
                )
    return None


def _module_action(text: str, instruction: str) -> EditAction | None:
    for label, flag_name in _MODULE_MAP.items():
        is_match = (
            bool(re.search(rf"\b{re.escape(label)}\b", text))
            if len(label) <= 3
            else label in text
        )
        if not is_match:
            continue
        if _has_any_verb(text, _ADD_VERBS):
            return EditAction(
                action_type=EditActionType.ADD_MODULE,
                target=flag_name,
                raw_instruction=instruction,
            )
        if _has_any_verb(text, _REMOVE_VERBS):
            return EditAction(
                action_type=EditActionType.REMOVE_MODULE,
                target=flag_name,
                raw_instruction=instruction,
            )
    return None


def _regex_kpi_action(text: str, instruction: str) -> EditAction | None:
    add_match = re.search(r"(?:add|include|show)\s+kpi\s+([\w\s]+)", text)
    if add_match:
        target = add_match.group(1).strip().replace("module", "").strip()
        return EditAction(
            action_type=EditActionType.ADD_KPI,
            target=target,
            raw_instruction=instruction,
        )

    remove_match = re.search(
        r"(?:remove|delete|hide|disable|drop)\s+kpi\s+([\w\s]+)", text
    )
    if remove_match:
        target = remove_match.group(1).strip().replace("module", "").strip()
        return EditAction(
            action_type=EditActionType.REMOVE_KPI,
            target=target,
            raw_instruction=instruction,
        )
    return None


def _v2_id_action(text: str, instruction: str) -> EditAction | None:
    queue_match = re.search(r"\bqueue\s+(\d+)\b", text)
    if queue_match:
        queue_id = queue_match.group(1)
        if _has_any_verb(text, _ADD_VERBS):
            return EditAction(
                action_type=EditActionType.ADD_QUEUE,
                target=queue_id,
                raw_instruction=instruction,
            )
        if _has_any_verb(text, _REMOVE_VERBS):
            return EditAction(
                action_type=EditActionType.REMOVE_QUEUE,
                target=queue_id,
                raw_instruction=instruction,
            )

    dashboard_match = re.search(r"\bdashboard\s+(\d+)\b", text)
    if dashboard_match:
        dashboard_id = dashboard_match.group(1)
        if _has_any_verb(text, _ADD_VERBS):
            return EditAction(
                action_type=EditActionType.ADD_DASHBOARD_BY_ID,
                target=dashboard_id,
                raw_instruction=instruction,
            )
        if _has_any_verb(text, _REMOVE_VERBS):
            return EditAction(
                action_type=EditActionType.REMOVE_DASHBOARD_BY_ID,
                target=dashboard_id,
                raw_instruction=instruction,
            )
    return None


def parse_edit_instruction(instruction: str, catalog: BundleCatalog) -> EditAction:
    """Parse a natural language instruction into a structured EditAction.

    Example inputs:
      "add a projects module"
      "remove the dashboard"
      "add avg resolution time kpi"
      "delete kpi SLA Compliance"

    Returns an EditAction. If parsing fails, EditActionType.UNSUPPORTED is used.
    """
    text = instruction.lower().strip()
    metrics_catalog = catalog.get_metrics_catalog()
    parsed = _dashboard_action(text, instruction)
    if parsed is not None:
        return parsed

    parsed = _v2_id_action(text, instruction)
    if parsed is not None:
        return parsed

    parsed = _kpi_action(text, instruction, metrics_catalog)
    if parsed is not None:
        return parsed

    parsed = _module_action(text, instruction)
    if parsed is not None:
        return parsed

    parsed = _regex_kpi_action(text, instruction)
    if parsed is not None:
        return parsed

    return EditAction(
        action_type=EditActionType.UNSUPPORTED, raw_instruction=instruction
    )
