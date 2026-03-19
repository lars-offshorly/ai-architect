from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from core.llm_factory import get_openai_chat_model
from core.logging_config import get_session_logger
from core.settings import get_settings

from .schemas import DummyDataJSON, GenerationJSON, RetrievedTemplate


_SCHEMA_VERSION = "1.0"

SYSTEM_PROMPT = (
    "You generate workspace configuration JSON and realistic sample data for a team onboarding preview.\n\n"
    "RULES:\n"
    "- Copy session_id, schema_version, bundle, entity_type, and generated_at EXACTLY from the input — do not alter them.\n"
    "- Enable only the modules listed in the template (enabled=true, config={}).\n"
    "- workspace_meta.team_size must be the integer from Filled Slots if present, else null.\n"
    "- workspace_meta.industry_hint must be the industry string from the input, else null.\n"
    "- In dummy_data_json.stores, populate ONLY stores that match the enabled modules with 4-6 realistic records each.\n"
    "- Records must reflect the user's actual industry, use case, and team size — not generic placeholders.\n"
    "- Leave stores for disabled modules as empty arrays.\n"
    "- generated_at must be copied verbatim from the input — do not change it.\n"
    "- Module-to-store key mapping (use the store key exactly as shown):\n"
    "    dashboard -> dashboard_widgets\n"
    "    tasks -> tasks\n"
    "    timelines -> tasks\n"
    "    milestones -> milestones\n"
    "    tickets -> tickets\n"
    "    queues -> queues\n"
    "    kpis -> kpis\n"
    "    assets -> assets\n"
    "    maintenance -> maintenance\n"
    "    work_orders -> tasks\n"
    "    scheduling -> tasks\n"
    "    forms -> tasks"
)


class PersonalisationInput(BaseModel):
    session_id: str
    bundle: str
    entity_type: str
    industry_hint: str | None = None
    filled_slots: dict[str, object] = Field(default_factory=dict)


class PersonalisationOutput(BaseModel):
    generation_json: GenerationJSON
    dummy_data_json: DummyDataJSON


@dataclass(frozen=True)
class ParsedSections:
    preamble: str
    sections: dict[str, list[str]]
    order: list[str]


def _parse_sections(content: str) -> ParsedSections:
    preamble_lines: list[str] = []
    sections: dict[str, list[str]] = {}
    order: list[str] = []
    current_section: str | None = None

    for line in content.splitlines():
        if line.startswith("## "):
            if current_section is not None:
                sections[current_section] = sections.get(current_section, [])
            current_section = line.strip()
            sections[current_section] = []
            order.append(current_section)
            continue

        if current_section is None:
            preamble_lines.append(line)
            continue

        sections[current_section].append(line)

    return ParsedSections(
        preamble="\n".join(preamble_lines).strip(),
        sections=sections,
        order=order,
    )


def _render_sections(parsed_sections: ParsedSections) -> str:
    blocks: list[str] = []
    if parsed_sections.preamble:
        blocks.append(parsed_sections.preamble)

    for header in parsed_sections.order:
        blocks.append(header)
        body = "\n".join(parsed_sections.sections.get(header, [])).strip()
        if body:
            blocks.append(body)

    return "\n\n".join(blocks).strip()


def _merge_markdown(base_content: str, overlay_content: str) -> str:
    base_sections = _parse_sections(base_content)
    overlay_sections = _parse_sections(overlay_content)

    merged_sections = dict(base_sections.sections)
    merged_order = list(base_sections.order)

    for header in overlay_sections.order:
        if header not in merged_order:
            merged_order.append(header)
        merged_sections[header] = overlay_sections.sections.get(header, [])

    return _render_sections(
        ParsedSections(
            preamble=base_sections.preamble,
            sections=merged_sections,
            order=merged_order,
        ),
    )


def _template_priority(template: RetrievedTemplate) -> tuple[int, float, str]:
    is_base = template.metadata.industry_hint == "base"
    return (0 if is_base else 1, template.score, template.metadata.industry_hint)


def _merge_templates(templates: list[RetrievedTemplate]) -> str:
    if not templates:
        return ""

    if len(templates) == 1:
        return templates[0].content

    sorted_templates = sorted(templates, key=_template_priority)
    merged_content = sorted_templates[0].content

    for template in sorted_templates[1:]:
        merged_content = _merge_markdown(merged_content, template.content)

    return merged_content


def _build_user_prompt(
    input_data: PersonalisationInput,
    merged_template_content: str,
    generated_at: str,
) -> str:
    slots_payload = json.dumps(input_data.filled_slots, sort_keys=True)
    industry_hint = input_data.industry_hint or "unknown"
    team_size = input_data.filled_slots.get("team_size")
    primary_use_case = input_data.filled_slots.get("primary_use_case", "general operations")
    return (
        "=== FIXED VALUES — copy verbatim into output ===\n"
        f"session_id: {input_data.session_id}\n"
        f"schema_version: {_SCHEMA_VERSION}\n"
        f"bundle: {input_data.bundle}\n"
        f"entity_type: {input_data.entity_type}\n"
        f"generated_at: {generated_at}\n\n"
        "=== USER CONTEXT — use to generate realistic data ===\n"
        f"Industry: {industry_hint}\n"
        f"Team size: {team_size if team_size is not None else 'unknown'}\n"
        f"Primary use case: {primary_use_case}\n"
        f"All filled slots: {slots_payload}\n\n"
        "=== TEMPLATE — defines enabled modules and sample structure ===\n"
        f"{merged_template_content}"
    )


async def personalise_template(
    templates: list[RetrievedTemplate],
    input_data: PersonalisationInput,
) -> PersonalisationOutput:
    session_logger = get_session_logger(__name__, input_data.session_id)
    session_logger.info(
        "Starting template personalisation for bundle=%s",
        input_data.bundle,
    )
    merged_template_content = _merge_templates(templates)
    if not merged_template_content:
        session_logger.error("No template content available for personalisation")
        raise ValueError("No template content available for personalisation.")

    generated_at = datetime.now(tz=timezone.utc).isoformat()
    settings = get_settings()
    model = get_openai_chat_model(temperature=settings.ASSEMBLER_TEMPERATURE)
    structured_model = model.with_structured_output(PersonalisationOutput, method="function_calling")

    prompt = _build_user_prompt(input_data, merged_template_content, generated_at)
    try:
        result = await structured_model.ainvoke(
            [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ],
        )
    except Exception as exc:
        session_logger.error("Template personalisation failed: %s", exc, exc_info=True)
        raise

    if isinstance(result, PersonalisationOutput):
        session_logger.info("Template personalisation completed successfully")
        return result

    if isinstance(result, dict):
        output = PersonalisationOutput.model_validate(result)
        session_logger.info("Template personalisation completed successfully")
        return output

    session_logger.error("Unexpected personalisation response type: %s", type(result))
    raise TypeError("Unexpected personalisation response type.")
