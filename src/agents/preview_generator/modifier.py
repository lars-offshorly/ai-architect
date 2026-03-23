from __future__ import annotations

import copy
import json

from core.logging import get_logger
from domain.models.extracted_info import ExtractedInfo

logger = get_logger(__name__)

_PLACEHOLDER_MAP = {
    "{{company_name}}": "company_name",
    "{{employee_name}}": "employee_names.0",
    "{{new_hire_name}}": "employee_names.1",
    "{{hr_manager}}": "role_names.0",
    "{{team_lead}}": "role_names.0",
    "{{team_member}}": "role_names.1",
    "{{project_name}}": "primary_use_case",
    "{{asset_name}}": "primary_use_case",
    "{{asset_name_2}}": "primary_use_case",
    "{{asset_category}}": "department_names.0",
    "{{location}}": "department_names.0",
    "{{technician}}": "employee_names.0",
    "{{technician_2}}": "employee_names.1",
    "{{zone}}": "department_names.0",
    "{{zone_2}}": "department_names.1",
    "{{client_name}}": "company_name",
    "{{client_name_2}}": "company_name",
    "{{task_title}}": "primary_use_case",
    "{{task_title_2}}": "primary_use_case",
    "{{assignee}}": "role_names.0",
}


def _resolve_value(extracted: ExtractedInfo, field_path: str) -> str | None:
    parts = field_path.split(".")
    field = parts[0]
    index = int(parts[1]) if len(parts) > 1 else None

    raw = getattr(extracted, field, None)
    if raw is None:
        return None
    if index is not None and isinstance(raw, list):
        return raw[index] if index < len(raw) else None
    if isinstance(raw, str):
        return raw
    return None


def _replace_placeholders(text: str, extracted: ExtractedInfo) -> str:
    for placeholder, field_path in _PLACEHOLDER_MAP.items():
        if placeholder in text:
            value = _resolve_value(extracted, field_path)
            if value:
                text = text.replace(placeholder, value)
    return text


def _inject_into_object(obj: object, extracted: ExtractedInfo) -> object:
    if isinstance(obj, str):
        return _replace_placeholders(obj, extracted)
    if isinstance(obj, dict):
        return {k: _inject_into_object(v, extracted) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_inject_into_object(item, extracted) for item in obj]
    return obj


class TemplateModifier:
    def inject(
        self,
        template: dict[str, object],
        extracted: ExtractedInfo,
    ) -> dict[str, object]:
        result = copy.deepcopy(template)
        modified = _inject_into_object(result, extracted)
        if isinstance(modified, dict):
            modified["session_id"] = extracted.session_id
            logger.info("Template injection complete for session=%s", extracted.session_id)
            return modified
        return result
