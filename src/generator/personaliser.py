"""Legacy template personalisation helpers."""

from __future__ import annotations

import json
from collections import OrderedDict

from pydantic import BaseModel, Field

from core.config import get_settings
from core.llm import get_openai_chat_model

from .schemas import DummyDataJSON, GenerationJSON, RetrievedTemplate


class PersonalisationInput(BaseModel):
    session_id: str
    bundle: str
    entity_type: str
    industry_hint: str
    filled_slots: dict[str, object] = Field(default_factory=dict)


class PersonalisationOutput(BaseModel):
    generation_json: GenerationJSON
    dummy_data_json: DummyDataJSON


def _merge_templates(templates: list[RetrievedTemplate]) -> str:
    if not templates:
        return ""
    if len(templates) == 1:
        return templates[0].content

    sections: OrderedDict[str, str] = OrderedDict()
    for template in templates:
        for heading, body in _split_sections(template.content).items():
            sections.setdefault(heading, body)

    return "\n\n".join(
        f"## {heading}\n\n{body}" if heading else body
        for heading, body in sections.items()
    )


def _split_sections(content: str) -> OrderedDict[str, str]:
    sections: OrderedDict[str, str] = OrderedDict()
    current_heading = ""
    current_lines: list[str] = []

    for line in content.splitlines():
        if line.startswith("## "):
            sections[current_heading] = "\n".join(current_lines).strip()
            current_heading = line.removeprefix("## ").strip()
            current_lines = []
            continue
        if line.startswith("# ") and not current_heading:
            continue
        current_lines.append(line)

    sections[current_heading] = "\n".join(current_lines).strip()
    return OrderedDict((heading, body) for heading, body in sections.items() if body)


def _build_user_prompt(
    input_data: PersonalisationInput,
    merged_template: str,
    generated_at: str,
) -> str:
    slots_json = json.dumps(input_data.filled_slots, sort_keys=True)
    return (
        f"session_id: {input_data.session_id}\n"
        f"bundle: {input_data.bundle}\n"
        f"entity_type: {input_data.entity_type}\n"
        f"industry_hint: {input_data.industry_hint}\n"
        f"generated_at: {generated_at}\n"
        f"filled_slots: {slots_json}\n\n"
        f"{merged_template}"
    )


async def personalise_template(
    templates: list[RetrievedTemplate],
    input_data: PersonalisationInput,
) -> PersonalisationOutput:
    generated_at = "2026-02-25T11:00:00+08:00"
    prompt = _build_user_prompt(input_data, _merge_templates(templates), generated_at)
    settings = get_settings()
    model = get_openai_chat_model(temperature=settings.ASSEMBLER_TEMPERATURE)
    structured_model = model.with_structured_output(PersonalisationOutput)
    result = await structured_model.ainvoke([prompt])
    if not isinstance(result, PersonalisationOutput):
        return PersonalisationOutput.model_validate(result)
    return result
