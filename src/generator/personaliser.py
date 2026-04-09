from __future__ import annotations

import json
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from core import get_openai_chat_model
from core.config import get_settings
from generator.schemas import DummyDataJSON, GenerationJSON, RetrievedTemplate


class PersonalisationInput(BaseModel):
    session_id: str
    bundle: str
    entity_type: str
    industry_hint: str | None = None
    filled_slots: dict[str, object] = Field(default_factory=dict)


class PersonalisationOutput(BaseModel):
    generation_json: GenerationJSON
    dummy_data_json: DummyDataJSON


def _split_sections(content: str) -> tuple[str, list[tuple[str, str]]]:
    lines = content.splitlines()
    preamble: list[str] = []
    sections: list[tuple[str, str]] = []
    current_heading: str | None = None
    current_lines: list[str] = []

    for line in lines:
        if line.startswith("## "):
            if current_heading is None:
                preamble = preamble if preamble else []
            else:
                sections.append((current_heading, "\n".join(current_lines).strip()))
            current_heading = line.strip()
            current_lines = []
            continue

        if current_heading is None:
            preamble.append(line)
        else:
            current_lines.append(line)

    if current_heading is not None:
        sections.append((current_heading, "\n".join(current_lines).strip()))
    return ("\n".join(preamble).strip(), sections)


def _merge_templates(templates: list[RetrievedTemplate]) -> str:
    if not templates:
        return ""
    if len(templates) == 1:
        return templates[0].content

    merged_preamble = ""
    order: list[str] = []
    section_map: dict[str, str] = {}
    for template in reversed(templates):
        preamble, sections = _split_sections(template.content)
        if preamble and not merged_preamble:
            merged_preamble = preamble
        for heading, body in sections:
            if heading not in order:
                order.append(heading)
            section_map[heading] = body

    chunks: list[str] = []
    if merged_preamble:
        chunks.append(merged_preamble)
    for heading in order:
        body = section_map[heading]
        chunks.append(heading)
        if body:
            chunks.append(body)
    return "\n\n".join(chunk for chunk in chunks if chunk.strip())


def _build_user_prompt(
    input_data: PersonalisationInput,
    merged_template_content: str,
    generated_at: str,
) -> str:
    slots_json = json.dumps(input_data.filled_slots, sort_keys=True)
    return (
        "Build structured workspace JSON from the template and onboarding context.\n"
        f"session_id: {input_data.session_id}\n"
        f"bundle: {input_data.bundle}\n"
        f"entity_type: {input_data.entity_type}\n"
        f"Industry: {input_data.industry_hint or ''}\n"
        f"generated_at: {generated_at}\n"
        f"All filled slots: {slots_json}\n"
        "\nMerged template:\n"
        f"{merged_template_content}"
    )


async def personalise_template(
    templates: list[RetrievedTemplate],
    input_data: PersonalisationInput,
) -> PersonalisationOutput:
    merged_content = _merge_templates(templates)
    generated_at = datetime.now(timezone.utc).isoformat()
    prompt = _build_user_prompt(input_data, merged_content, generated_at)
    settings = get_settings()
    model = get_openai_chat_model(temperature=settings.ASSEMBLER_TEMPERATURE)
    structured = model.with_structured_output(PersonalisationOutput)
    result = await structured.ainvoke([HumanMessage(content=prompt)])
    if isinstance(result, PersonalisationOutput):
        return result
    return PersonalisationOutput.model_validate(result)
