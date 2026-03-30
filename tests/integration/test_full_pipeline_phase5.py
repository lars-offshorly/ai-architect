from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import pytest
from generator.personaliser import PersonalisationOutput
from generator.schemas import (
    DummyDataJSON,
    GenerationJSON,
    ModuleConfig,
    StoreData,
    WorkspaceMeta,
)
from httpx import ASGITransport, AsyncClient
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from api.app import create_app
from onboarding.states import OnboardingIntents, TurnClassification


@dataclass
class TestSettings:
    DEBUG: bool = True
    RATE_LIMIT_PER_MINUTE: int = 30


async def _fake_database_initialize() -> None:
    return None


async def _fake_database_close() -> None:
    return None


def _fake_pinecone_initialize() -> None:
    return None


async def _fake_pinecone_close() -> None:
    return None


@asynccontextmanager
async def _fake_get_checkpointer(
    memory: InMemorySaver,
) -> AsyncIterator[InMemorySaver]:
    yield memory


def _extract_prompt_value(prompt: str, prefix: str) -> str:
    for line in prompt.splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix).strip()
    return ""


def _load_slots(payload: str) -> dict[str, object]:
    try:
        loaded = json.loads(payload)
    except json.JSONDecodeError:
        return {}
    if isinstance(loaded, dict):
        return {str(key): loaded[key] for key in loaded}
    return {}


def _build_personalisation_output(
    session_id: str,
    bundle: str,
    entity_type: str,
    industry_hint: str | None,
    slots: dict[str, object],
) -> PersonalisationOutput:
    if bundle == "hr_hub":
        modules = [
            ModuleConfig(module_key="tickets", enabled=True, config={}),
            ModuleConfig(module_key="queues", enabled=True, config={}),
            ModuleConfig(module_key="kpis", enabled=True, config={}),
            ModuleConfig(module_key="dashboard", enabled=True, config={}),
        ]
        stores = StoreData(
            tickets=[{"id": "T-1", "title": "Candidate onboarding"}],
            queues=[{"id": "Q-1", "name": "People Ops"}],
            kpis=[{"label": "time_to_hire", "value": 14}],
            dashboard_widgets=[{"widget": "hiring_summary"}],
        )
    else:
        modules = [
            ModuleConfig(module_key="tickets", enabled=True, config={}),
            ModuleConfig(module_key="dashboard", enabled=True, config={}),
        ]
        stores = StoreData(
            tickets=[{"id": "T-9", "title": "General request"}],
            dashboard_widgets=[{"widget": "open_requests"}],
        )

    team_size_value = slots.get("team_size")
    team_size = team_size_value if isinstance(team_size_value, int) else None
    workspace_meta = WorkspaceMeta(
        team_size=team_size,
        industry_hint=industry_hint,
        generated_at="2026-02-25T17:00:00+08:00",
    )
    return PersonalisationOutput(
        generation_json=GenerationJSON(
            schema_version="1.0",
            session_id=session_id,
            bundle=bundle,
            entity_type=entity_type,
            modules=modules,
            workspace_meta=workspace_meta,
        ),
        dummy_data_json=DummyDataJSON(
            schema_version="1.0",
            session_id=session_id,
            bundle=bundle,
            stores=stores,
        ),
    )


class FakeStructuredModel:
    def __init__(self, schema: type[object]) -> None:
        self._schema = schema

    async def ainvoke(self, messages: list[object]) -> object:
        message_text = str(getattr(messages[-1], "content", "")).strip()
        lowered = message_text.lower()

        if self._schema is TurnClassification:
            if lowered in {"yes", "y", "confirm"}:
                return TurnClassification(
                    turn_type="bundle_confirmation",
                    extracted_answer="",
                )
            if (
                "tech agency" in lowered
                or "workspace" in lowered
                or "fintech" in lowered
            ):
                return TurnClassification(
                    turn_type="new_onboarding",
                    extracted_answer="",
                )
            return TurnClassification(
                turn_type="clarification_answer",
                extracted_answer=message_text,
            )

        if self._schema is OnboardingIntents:
            if "tech agency" in lowered:
                return OnboardingIntents(
                    raw_intent="run a 12-person tech agency",
                    entity_type="people",
                    bundle="hr_hub",
                    inferred_modules=["tickets", "queues", "kpis", "dashboard"],
                    explicit_modules=["tickets"],
                    industry_hint="tech_agency",
                    confidence=0.92,
                )
            if "fintech" in lowered:
                return OnboardingIntents(
                    raw_intent="fintech people operations",
                    entity_type="people",
                    bundle="hr_hub",
                    inferred_modules=[
                        "tickets",
                        "queues",
                        "kpis",
                        "dashboard",
                    ],
                    explicit_modules=["tickets"],
                    industry_hint="fintech",
                    confidence=0.74,
                )
            return OnboardingIntents(
                raw_intent="ad hoc request handling",
                entity_type="work",
                bundle="generic",
                inferred_modules=["tickets", "dashboard"],
                explicit_modules=["tickets"],
                industry_hint="unknown",
                confidence=0.63,
            )

        if self._schema is PersonalisationOutput:
            session_id = _extract_prompt_value(message_text, "session_id: ")
            bundle = _extract_prompt_value(message_text, "bundle: ") or "generic"
            entity_type = (
                _extract_prompt_value(message_text, "entity_type: ") or "work"
            )
            industry_hint = _extract_prompt_value(message_text, "Industry: ")
            slots_payload = _extract_prompt_value(message_text, "All filled slots: ")
            slots = _load_slots(slots_payload)
            return _build_personalisation_output(
                session_id=session_id,
                bundle=bundle,
                entity_type=entity_type,
                industry_hint=industry_hint,
                slots=slots,
            )

        raise AssertionError("Unexpected structured output schema")


class FakeChatModel:
    def with_structured_output(self, schema: type[object], **kwargs: object) -> FakeStructuredModel:
        return FakeStructuredModel(schema)

    async def ainvoke(self, messages: list[object]) -> AIMessage:
        prompt_text = str(getattr(messages[-1], "content", ""))
        if "Target slot: team_size" in prompt_text:
            return AIMessage(content="How many people are in your team?")
        return AIMessage(
            content="I recommend this bundle with its default modules. Does this look right?",
        )


def _fake_model_factory(**kwargs: object) -> FakeChatModel:
    _ = kwargs
    return FakeChatModel()


def _template_document(
    bundle: str,
    industry_hint: str,
    modules: list[str],
    required_slots: list[str],
) -> dict[str, object]:
    return {
        "id": f"{bundle}__{industry_hint}",
        "score": 1.0,
        "metadata": {
            "bundle": bundle,
            "industry_hint": industry_hint,
            "modules": modules,
            "required_slots": required_slots,
            "version": "1.0",
            "content": (
                "---\n"
                f"bundle: {bundle}\n"
                f"industry_hint: {industry_hint}\n"
                "version: '1.0'\n"
                "---\n"
                "## Tickets\n"
                "- title: {{primary_use_case}}\n"
            ),
        },
    }


def _search_match(
    bundle: str,
    industry_hint: str,
    modules: list[str],
    required_slots: list[str],
) -> dict[str, object]:
    return {
        "score": 0.88,
        "page_content": "## Tickets\n- title: {{primary_use_case}}\n",
        "metadata": {
            "bundle": bundle,
            "industry_hint": industry_hint,
            "modules": modules,
            "required_slots": required_slots,
            "version": "1.0",
            "content": "## Tickets\n- title: {{primary_use_case}}\n",
        },
    }


async def _fake_fetch_documents(
    ids: list[str],
    namespace: str,
) -> list[dict[str, object]]:
    _ = namespace
    documents = {
        "hr_hub__tech_agency": _template_document(
            bundle="hr_hub",
            industry_hint="tech_agency",
            modules=["tickets", "queues", "kpis", "dashboard"],
            required_slots=["team_size", "primary_use_case"],
        ),
        "generic__base": _template_document(
            bundle="generic",
            industry_hint="base",
            modules=["tickets", "dashboard"],
            required_slots=["primary_use_case"],
        ),
    }
    return [documents[doc_id] for doc_id in ids if doc_id in documents]


async def _fake_search(
    query: str,
    top_k: int,
    namespace: str,
) -> list[dict[str, object]]:
    _ = (query, top_k, namespace)
    return []


def _patch_app_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("api.app.Database.initialize", _fake_database_initialize)
    monkeypatch.setattr("api.app.Database.close", _fake_database_close)
    monkeypatch.setattr(
        "api.app.pinecone_client.initialize",
        _fake_pinecone_initialize,
    )
    monkeypatch.setattr("api.app.pinecone_client.close", _fake_pinecone_close)


def _patch_settings(monkeypatch: pytest.MonkeyPatch, settings: TestSettings) -> None:
    monkeypatch.setattr("api.middleware.auth.get_settings", lambda: settings)
    monkeypatch.setattr("api.middleware.rate_limiter.get_settings", lambda: settings)


def _patch_pipeline_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    memory: InMemorySaver,
) -> None:
    import sys
    cc_mod = sys.modules["onboarding.nodes.conversation_classifier"]
    ie_mod = sys.modules["onboarding.nodes.intent_extraction"]
    cl_mod = sys.modules["onboarding.nodes.clarification"]
    bc_mod = sys.modules["onboarding.nodes.bundle_confirmer"]

    monkeypatch.setattr(
        "onboarding.processor.Database.initialize",
        _fake_database_initialize,
    )
    monkeypatch.setattr(
        "onboarding.processor.Database.get_checkpointer",
        lambda: _fake_get_checkpointer(memory),
    )
    monkeypatch.setattr(cc_mod, "get_openai_chat_model", _fake_model_factory)
    monkeypatch.setattr(ie_mod, "get_openai_chat_model", _fake_model_factory)
    monkeypatch.setattr(cl_mod, "get_openai_chat_model", _fake_model_factory)
    monkeypatch.setattr(bc_mod, "get_openai_chat_model", _fake_model_factory)

    monkeypatch.setattr(
        "generator.personaliser.get_openai_chat_model",
        _fake_model_factory,
    )
    monkeypatch.setattr(
        "generator.retriever.pinecone_client.fetch_documents",
        _fake_fetch_documents,
    )
    monkeypatch.setattr(
        "generator.retriever.pinecone_client.search",
        _fake_search,
    )


@pytest.mark.asyncio
async def test_full_pipeline_hr_hub_via_api(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = TestSettings(DEBUG=True, RATE_LIMIT_PER_MINUTE=30)
    memory = InMemorySaver()
    _patch_app_dependencies(monkeypatch)
    _patch_settings(monkeypatch, settings)
    _patch_pipeline_dependencies(monkeypatch, memory)

    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        started = await client.post(
            "/onboard",
            json={"message": "I run a 12-person tech agency"},
        )

        assert started.status_code == 200
        started_payload = started.json()
        assert started_payload["status"] == "awaiting_input"
        assert started_payload["interrupt"]["slot"] == "team_size"

        session_id = str(started_payload["session_id"])
        after_clarification = await client.post(
            f"/onboard/{session_id}/reply",
            json={"message": "12"},
        )

        assert after_clarification.status_code == 200
        clarification_payload = after_clarification.json()
        assert clarification_payload["status"] == "awaiting_input"
        assert clarification_payload["interrupt"]["type"] == "bundle_suggestion"

        completed = await client.post(
            f"/onboard/{session_id}/reply",
            json={"message": "yes"},
        )

    assert completed.status_code == 200
    completed_payload = completed.json()
    assert completed_payload["status"] == "complete"
    assert completed_payload["generation_json"]["bundle"] == "hr_hub"
    assert completed_payload["dummy_data_json"]["stores"]["tickets"]


@pytest.mark.asyncio
async def test_full_pipeline_generic_via_api(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = TestSettings(DEBUG=True, RATE_LIMIT_PER_MINUTE=30)
    memory = InMemorySaver()
    _patch_app_dependencies(monkeypatch)
    _patch_settings(monkeypatch, settings)
    _patch_pipeline_dependencies(monkeypatch, memory)

    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        started = await client.post(
            "/onboard",
            json={"message": "I need a workspace for ad hoc requests"},
        )

        assert started.status_code == 200
        started_payload = started.json()
        assert started_payload["status"] == "awaiting_input"
        assert started_payload["interrupt"]["type"] == "bundle_suggestion"

        session_id = str(started_payload["session_id"])
        completed = await client.post(
            f"/onboard/{session_id}/reply",
            json={"message": "yes"},
        )

    assert completed.status_code == 200
    completed_payload = completed.json()
    assert completed_payload["status"] == "complete"
    assert completed_payload["generation_json"]["bundle"] == "generic"
    assert completed_payload["dummy_data_json"]["stores"]["dashboard_widgets"]


@pytest.mark.asyncio
async def test_full_pipeline_search_fallback_via_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = TestSettings(DEBUG=True, RATE_LIMIT_PER_MINUTE=30)
    memory = InMemorySaver()
    search_queries: list[str] = []

    async def _search_hit(
        query: str,
        top_k: int,
        namespace: str,
    ) -> list[dict[str, object]]:
        _ = (top_k, namespace)
        search_queries.append(query)
        return [
            _search_match(
                bundle="hr_hub",
                industry_hint="fintech",
                modules=["tickets", "queues", "kpis", "dashboard"],
                required_slots=["team_size", "primary_use_case"],
            ),
        ]

    _patch_app_dependencies(monkeypatch)
    _patch_settings(monkeypatch, settings)
    _patch_pipeline_dependencies(monkeypatch, memory)
    monkeypatch.setattr(
        "generator.retriever.pinecone_client.search",
        _search_hit,
    )

    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        started = await client.post(
            "/onboard",
            json={"message": "I lead people operations for a fintech team"},
        )

        assert started.status_code == 200
        started_payload = started.json()
        assert started_payload["status"] == "awaiting_input"
        assert started_payload["interrupt"]["slot"] == "team_size"

        session_id = str(started_payload["session_id"])
        after_clarification = await client.post(
            f"/onboard/{session_id}/reply",
            json={"message": "25"},
        )

        assert after_clarification.status_code == 200
        assert after_clarification.json()["interrupt"]["type"] == "bundle_suggestion"

        completed = await client.post(
            f"/onboard/{session_id}/reply",
            json={"message": "yes"},
        )

    assert completed.status_code == 200
    completed_payload = completed.json()
    assert completed_payload["status"] == "complete"
    assert completed_payload["generation_json"]["bundle"] == "hr_hub"
    assert search_queries
