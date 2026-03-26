from __future__ import annotations

from types import SimpleNamespace

import pytest
from generator.personaliser import (
    PersonalisationInput,
    PersonalisationOutput,
    _build_user_prompt,
    _merge_templates,
    personalise_template,
)
from generator.schemas import (
    DummyDataJSON,
    GenerationJSON,
    ModuleConfig,
    RetrievedTemplate,
    StoreData,
    TemplateMetadata,
    WorkspaceMeta,
)


def _template(
    industry_hint: str,
    content: str,
    score: float = 1.0,
) -> RetrievedTemplate:
    metadata = TemplateMetadata(
        bundle="hr_hub",
        industry_hint=industry_hint,
        modules=["tickets", "queues", "kpis", "dashboard"],
        required_slots=["team_size", "primary_use_case"],
        version="1.0",
        content=content,
    )
    return RetrievedTemplate(
        metadata=metadata,
        content=content,
        score=score,
        source="fetch",
    )


def _personalisation_input() -> PersonalisationInput:
    return PersonalisationInput(
        session_id="session-123",
        bundle="hr_hub",
        entity_type="people",
        industry_hint="tech_agency",
        filled_slots={"team_size": 12, "primary_use_case": "onboarding"},
    )


def _personalisation_output() -> PersonalisationOutput:
    return PersonalisationOutput(
        generation_json=GenerationJSON(
            schema_version="1.0",
            session_id="session-123",
            bundle="hr_hub",
            entity_type="people",
            modules=[
                ModuleConfig(module_key="tickets", enabled=True, config={}),
                ModuleConfig(module_key="queues", enabled=True, config={}),
                ModuleConfig(module_key="kpis", enabled=True, config={}),
                ModuleConfig(module_key="dashboard", enabled=True, config={}),
            ],
            workspace_meta=WorkspaceMeta(
                team_size=12,
                industry_hint="tech_agency",
                generated_at="2026-02-25T11:00:00+08:00",
            ),
        ),
        dummy_data_json=DummyDataJSON(
            schema_version="1.0",
            session_id="session-123",
            bundle="hr_hub",
            stores=StoreData(
                tickets=[{"id": 1, "title": "ticket"}],
                queues=[{"id": 1, "name": "queue"}],
                kpis=[{"label": "kpi"}],
                dashboard_widgets=[{"widget": "summary"}],
            ),
        ),
    )


def test_merge_templates_single_template_returns_as_is() -> None:
    template = _template("base", "# Template\n\n## Tickets\n\n- title: Base")

    merged_content = _merge_templates([template])

    assert merged_content == template.content


def test_merge_templates_overlay_takes_precedence() -> None:
    base_template = _template(
        "base",
        "# Base\n\n## Tickets\n\n- title: Base ticket\n\n## KPIs\n\n- label: Base KPI",
        score=0.9,
    )
    overlay_template = _template(
        "tech_agency",
        "# Overlay\n\n## Tickets\n\n- title: Agency ticket",
        score=0.95,
    )

    merged_content = _merge_templates([overlay_template, base_template])

    assert "Agency ticket" in merged_content
    assert "Base ticket" not in merged_content
    assert "Base KPI" in merged_content


def test_build_user_prompt_includes_slots_and_bundle() -> None:
    input_data = _personalisation_input()

    prompt = _build_user_prompt(input_data, "Merged template content", "2026-02-25T11:00:00+08:00")

    assert "bundle: hr_hub" in prompt
    assert '"team_size": 12' in prompt
    assert "Merged template content" in prompt


@pytest.mark.asyncio
async def test_personalise_template_returns_structured_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_output = _personalisation_output()

    class FakeStructuredModel:
        async def ainvoke(self, messages: list[object]) -> PersonalisationOutput:
            return expected_output

    class FakeChatModel:
        def with_structured_output(
            self,
            schema: type[PersonalisationOutput],
            **kwargs: object,
        ) -> FakeStructuredModel:
            assert schema is PersonalisationOutput
            return FakeStructuredModel()

    monkeypatch.setattr(
        "generator.personaliser.get_settings",
        lambda: SimpleNamespace(ASSEMBLER_TEMPERATURE=0.2),
    )
    monkeypatch.setattr(
        "generator.personaliser.get_openai_chat_model",
        lambda **kwargs: FakeChatModel(),
    )

    templates = [_template("base", "# Template\n\n## Tickets\n\n- title: Ticket")]
    result = await personalise_template(templates, _personalisation_input())

    assert result == expected_output
