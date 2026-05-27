"""Edit sub-graph node: parses natural language instructions into EditAction schemas.

Currently uses heuristic keyword matching.
Phase 2: replace with a lightweight LLM call or a better semantic parser.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from dataclasses import dataclass

from langchain_openai import ChatOpenAI

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
_MAX_INSTRUCTION_LEN = 500
_EDIT_ACTION_NAMES = ", ".join(action.value for action in EditActionType)


@dataclass
class _FallbackCircuitBreaker:
    failures: int = 0
    opened_until_epoch: float = 0.0

    def allow(self) -> bool:
        return time.time() >= self.opened_until_epoch

    def success(self) -> None:
        self.failures = 0
        self.opened_until_epoch = 0.0

    def failure(self, *, threshold: int, cooldown_sec: int) -> None:
        self.failures += 1
        if self.failures >= threshold:
            self.opened_until_epoch = time.time() + float(cooldown_sec)
            self.failures = 0


_CIRCUIT = _FallbackCircuitBreaker()


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


def _dashboard_name_action(text: str, instruction: str) -> EditAction | None:
    remove_match = re.search(
        r"(?:remove|delete|hide|disable|drop)\s+(?:the\s+)?(.+?)\s+dashboard\b",
        text,
    )
    if remove_match:
        target = remove_match.group(1).strip()
        if target and target not in {"a", "an", "the"}:
            return EditAction(
                action_type=EditActionType.REMOVE_DASHBOARD,
                target=target,
                raw_instruction=instruction,
            )

    add_match = re.search(
        r"(?:add|enable|show|include)\s+(?:the\s+)?(.+?)\s+dashboard\b",
        text,
    )
    if add_match:
        target = add_match.group(1).strip()
        if target and target not in {"a", "an", "the"}:
            return EditAction(
                action_type=EditActionType.ADD_DASHBOARD,
                target=target,
                raw_instruction=instruction,
            )
    return None


def _queue_name_action(text: str, instruction: str) -> EditAction | None:
    remove_match = re.search(
        r"(?:remove|delete|hide|disable|drop)\s+(?:the\s+)?(.+?)\s+queue\b",
        text,
    )
    if remove_match:
        target = remove_match.group(1).strip()
        if target and target not in {"a", "an", "the"}:
            return EditAction(
                action_type=EditActionType.REMOVE_QUEUE,
                target=target,
                raw_instruction=instruction,
            )
    add_match = re.search(
        r"(?:add|enable|show|include)\s+(?:the\s+)?(.+?)\s+queue\b",
        text,
    )
    if add_match:
        target = add_match.group(1).strip()
        if target and target not in {"a", "an", "the"}:
            return EditAction(
                action_type=EditActionType.ADD_QUEUE,
                target=target,
                raw_instruction=instruction,
            )
    return None


def _kpi_name_action(text: str, instruction: str) -> EditAction | None:
    remove_match = re.search(
        r"(?:remove|delete|hide|disable|drop)\s+(?:the\s+)?(.+?)\s+kpi\b",
        text,
    )
    if remove_match:
        target = remove_match.group(1).strip()
        if target and target not in {"a", "an", "the"}:
            return EditAction(
                action_type=EditActionType.REMOVE_KPI,
                target=target,
                raw_instruction=instruction,
            )

    add_match = re.search(
        r"(?:add|enable|show|include)\s+(?:the\s+)?(.+?)\s+kpi\b",
        text,
    )
    if add_match:
        target = add_match.group(1).strip()
        if target and target not in {"a", "an", "the"}:
            return EditAction(
                action_type=EditActionType.ADD_KPI,
                target=target,
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
    parsed = _v2_id_action(text, instruction)
    if parsed is not None:
        return parsed

    parsed = _dashboard_name_action(text, instruction)
    if parsed is not None:
        return parsed

    parsed = _dashboard_action(text, instruction)
    if parsed is not None:
        return parsed

    parsed = _kpi_action(text, instruction, metrics_catalog)
    if parsed is not None:
        return parsed

    parsed = _queue_name_action(text, instruction)
    if parsed is not None:
        return parsed

    parsed = _kpi_name_action(text, instruction)
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


def _try_parse_json_action(raw: str, instruction: str) -> EditAction | None:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    action_name = parsed.get("action_type")
    target = parsed.get("target")
    if not isinstance(action_name, str):
        return None
    try:
        action_type = EditActionType(action_name)
    except ValueError:
        return None
    return EditAction(
        action_type=action_type,
        target=target if isinstance(target, str) else None,
        raw_instruction=instruction,
    )


def llm_parse_edit_instruction(
    instruction: str,
    model: ChatOpenAI,
) -> EditAction:
    clipped = instruction[:_MAX_INSTRUCTION_LEN]
    prompt = (
        "Convert user edit instruction into JSON with keys action_type,target.\n"
        f"Allowed action_type values: {_EDIT_ACTION_NAMES}.\n"
        "Rules:\n"
        "- Return only JSON object.\n"
        "- target must be string or null.\n"
        "- If unsure, use action_type='unsupported'.\n"
        f"Instruction: {clipped}\n"
        'Output example: {"action_type":"remove_queue","target":"101"}'
    )
    response = model.invoke(prompt)
    content = response.content if hasattr(response, "content") else str(response)
    if isinstance(content, list):
        content = "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    if not isinstance(content, str):
        return EditAction(
            action_type=EditActionType.UNSUPPORTED,
            raw_instruction=instruction,
        )
    action = _try_parse_json_action(content.strip(), instruction)
    if action is not None:
        return action
    return EditAction(
        action_type=EditActionType.UNSUPPORTED,
        raw_instruction=instruction,
    )


def parse_edit_instruction_with_fallback(
    instruction: str,
    catalog: BundleCatalog,
    *,
    llm_parser: Callable[[str], EditAction] | None = None,
    enabled: bool = False,
    timeout_ms: int = 1200,
    max_retries: int = 1,
    cb_threshold: int = 3,
    cb_cooldown_sec: int = 30,
) -> EditAction:
    rule_action = parse_edit_instruction(instruction, catalog)
    if rule_action.action_type != EditActionType.UNSUPPORTED:
        return rule_action
    if not enabled or llm_parser is None:
        return rule_action
    if not _CIRCUIT.allow():
        logger.warning(
            "edit_llm_fallback_skipped circuit_open instruction=%s", instruction
        )
        return rule_action

    for attempt in range(max_retries + 1):
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(llm_parser, instruction)
                action = future.result(timeout=timeout_ms / 1000.0)
            if not isinstance(action, EditAction):
                raise TypeError("llm_parser returned non-EditAction")
            if action.action_type == EditActionType.UNSUPPORTED:
                _CIRCUIT.success()
                return rule_action
            _CIRCUIT.success()
            logger.info(
                "edit_llm_fallback_success attempt=%s action=%s target=%s",
                attempt + 1,
                action.action_type.value,
                action.target,
            )
            return action
        except FuturesTimeoutError:
            _CIRCUIT.failure(threshold=cb_threshold, cooldown_sec=cb_cooldown_sec)
            logger.warning(
                "edit_llm_fallback_timeout attempt=%s timeout_ms=%s",
                attempt + 1,
                timeout_ms,
            )
        except Exception as exc:  # pylint: disable=broad-except
            _CIRCUIT.failure(threshold=cb_threshold, cooldown_sec=cb_cooldown_sec)
            logger.warning(
                "edit_llm_fallback_error attempt=%s err=%s",
                attempt + 1,
                type(exc).__name__,
            )
    return rule_action
