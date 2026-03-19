from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from generator.personaliser import PersonalisationOutput
from generator.schemas import (
    DummyDataJSON,
    GenerationJSON,
    ModuleConfig,
    StoreData,
    WorkspaceMeta,
)
from onboarding.processor import OnboardingProcessor
from onboarding.states import OnboardingIntents, TurnClassification


class FakeStructuredModel:
    def __init__(self, schema: type[object]) -> None:
        self._schema = schema

    async def ainvoke(self, messages: list[object]) -> object:
        user_text = str(getattr(messages[-1], "content", "")).lower()
        if self._schema is TurnClassification:
            if "tech agency" in user_text:
                return TurnClassification(
                    turn_type="new_onboarding",
                    extracted_answer="",
                )
            if user_text.strip() in {"yes", "y", "confirm"}:
                return TurnClassification(
                    turn_type="bundle_confirmation",
                    extracted_answer="",
                )
            return TurnClassification(
                turn_type="clarification_answer",
                extracted_answer=user_text,
            )

        if self._schema is OnboardingIntents:
            return OnboardingIntents(
                raw_intent="run a 12-person tech agency",
                entity_type="people",
                bundle="hr_hub",
                inferred_modules=["tickets", "queues", "kpis", "dashboard"],
                explicit_modules=["tickets"],
                industry_hint="tech_agency",
                confidence=0.92,
            )

        raise AssertionError("Unexpected structured schema")


async def _fake_initialize() -> None:
    return None


@asynccontextmanager
async def _fake_get_checkpointer(memory: InMemorySaver) -> AsyncIterator[InMemorySaver]:
    yield memory


async def _fake_retrieve_template(
    bundle: str,
    industry_hint: str | None,
) -> list[dict[str, object]]:
    return [{"bundle": bundle, "industry_hint": industry_hint or "base"}]


async def _fake_personalise_template(
    templates: list[dict[str, object]],
    input_data: object,
) -> PersonalisationOutput:
    session_id = str(getattr(input_data, "session_id", ""))
    return _fake_personalisation_output(session_id)


def _fake_validate_output(*args: object, **kwargs: object) -> None:
    return None


def _patch_onboarding_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    memory: InMemorySaver,
) -> None:
    import sys
    cc_mod = sys.modules["onboarding.nodes.conversation_classifier"]
    ie_mod = sys.modules["onboarding.nodes.intent_extraction"]
    cl_mod = sys.modules["onboarding.nodes.clarification"]
    bc_mod = sys.modules["onboarding.nodes.bundle_confirmer"]
    ja_mod = sys.modules["onboarding.nodes.json_assembler"]

    monkeypatch.setattr("onboarding.processor.Database.initialize", _fake_initialize)
    monkeypatch.setattr(
        "onboarding.processor.Database.get_checkpointer",
        lambda: _fake_get_checkpointer(memory),
    )
    monkeypatch.setattr(cc_mod, "get_openai_chat_model", _fake_model_factory)
    monkeypatch.setattr(ie_mod, "get_openai_chat_model", _fake_model_factory)
    monkeypatch.setattr(cl_mod, "get_openai_chat_model", _fake_model_factory)
    monkeypatch.setattr(bc_mod, "get_openai_chat_model", _fake_model_factory)

    monkeypatch.setattr(ja_mod, "retrieve_template", _fake_retrieve_template)
    monkeypatch.setattr(ja_mod, "personalise_template", _fake_personalise_template)
    monkeypatch.setattr(ja_mod, "validate_output", _fake_validate_output)


class FakeChatModel:
    def with_structured_output(self, schema: type[object]) -> FakeStructuredModel:
        return FakeStructuredModel(schema)

    async def ainvoke(self, messages: list[object]) -> AIMessage:
        prompt_text = str(getattr(messages[-1], "content", ""))
        if "Target slot:" in prompt_text:
            return AIMessage(content="How many people are in your team?")
        return AIMessage(
            content=(
                "I recommend HR Hub with tickets, queues, kpis, and dashboard. "
                "Does this look right?"
            ),
        )


def _fake_model_factory(**kwargs: object) -> FakeChatModel:
    return FakeChatModel()


def _fake_personalisation_output(session_id: str) -> PersonalisationOutput:
    return PersonalisationOutput(
        generation_json=GenerationJSON(
            schema_version="1.0",
            session_id=session_id,
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
                generated_at="2026-02-25T15:00:00+08:00",
            ),
        ),
        dummy_data_json=DummyDataJSON(
            schema_version="1.0",
            session_id=session_id,
            bundle="hr_hub",
            stores=StoreData(
                tickets=[{"id": 1, "title": "Candidate onboarding"}],
                queues=[{"id": 1, "name": "People Ops"}],
                kpis=[{"label": "time_to_hire"}],
                dashboard_widgets=[{"widget": "hiring_summary"}],
            ),
        ),
    )


@pytest.mark.asyncio
async def test_onboarding_flow_hr_hub(monkeypatch: pytest.MonkeyPatch) -> None:
    memory = InMemorySaver()
    _patch_onboarding_dependencies(monkeypatch, memory)

    processor = OnboardingProcessor()
    started = await processor.start_session("I run a 12-person tech agency")

    assert started["status"] == "awaiting_input"
    assert started["interrupt"] == {
        "question": "How many people are in your team?",
        "slot": "team_size",
    }

    session_id = str(started["session_id"])
    after_clarification = await processor.reply(session_id, "12")

    assert after_clarification["status"] == "awaiting_input"
    assert after_clarification["interrupt"]["type"] == "bundle_suggestion"

    completed = await processor.reply(session_id, "yes")

    assert completed["status"] == "complete"
    assert completed["generation_json"]["bundle"] == "hr_hub"
    assert completed["dummy_data_json"]["stores"]["tickets"]
