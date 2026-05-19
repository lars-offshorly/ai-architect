from __future__ import annotations

import asyncio
import inspect
from types import SimpleNamespace

from agents.interpreter.service import InterpreterService
from domain.models.bundle import BundleSuggestion
from domain.models.classification_result import ClassificationResult
from domain.models.interpreter_request import InterpreterRequest


def test_interpret_returns_extraction_result_type() -> None:
    """InterpreterService.interpret() must return ExtractionResult."""

    sig = inspect.signature(InterpreterService.interpret)
    # Return annotation should reference ExtractionResult
    hints = sig.return_annotation
    assert "ExtractionResult" in str(hints)


def test_variant_selector_is_not_runtime_dependency() -> None:
    assert not hasattr(InterpreterService, "_apply_variant_selection")


def test_interpret_uses_registry_facade_not_classifier() -> None:
    """Guard: runtime path must resolve via RegistryFacade, not Classifier.

    Constructs a service with both a stub classifier and a stub registry
    facade. interpret() must call the facade and never touch the classifier.
    """
    classifier_calls: list[str] = []
    facade_calls: list[str] = []

    selected = BundleSuggestion(
        bundle_key="generic",
        display_name="Custom Workspace",
        confidence=1.0,
    )
    facade_result = ClassificationResult(
        session_id="s1",
        selected_bundle=selected,
        ranked_candidates=[selected],
        confidence_status="proceed",
        top_confidence=1.0,
    )

    service = object.__new__(InterpreterService)
    service._bundle_keys = ["generic"]
    service._extractor = None  # forces the deterministic-stub branch
    service._classifier = SimpleNamespace(
        classify=lambda *a, **kw: classifier_calls.append("called") or facade_result
    )
    service._summarizer = None
    service._llm_industry_classifier = None
    service._registry_facade = SimpleNamespace(
        resolve_bundle=lambda **kw: facade_calls.append(kw["session_id"])
        or facade_result
    )

    request = InterpreterRequest(session_id="s1", user_message="hello", history=[])
    _extracted, suggested = asyncio.run(service.interpret(request))

    assert facade_calls == ["s1"]
    assert classifier_calls == []
    assert suggested.selected_bundle is not None
    assert suggested.selected_bundle.bundle_key == "generic"


def test_interpret_runtime_does_not_call_variant_selector() -> None:
    """Guard: variant_selector module must not be imported by service module."""
    import agents.interpreter.service as service_mod

    source = inspect.getsource(service_mod)
    assert "variant_selector" not in source
    assert "select_variant" not in source


def test_interpret_falls_back_to_llm_when_alias_resolver_misses() -> None:
    """Stage 2: when the alias resolver returns None, the LLM classifier runs."""
    from agents.interpreter.llm_industry_classifier import IndustryChoice

    facade_calls: list[str] = []
    llm_calls: list[str] = []

    async def fake_llm_classify(
        *, session_id: str, user_message: str, extracted: object
    ) -> IndustryChoice:
        await asyncio.sleep(0)
        llm_calls.append(session_id)
        return IndustryChoice(
            industry="bpo_contact_center",
            confidence=0.82,
            reasoning="User described support ticket workflow",
        )

    service = object.__new__(InterpreterService)
    service._bundle_keys = ["ticketing", "generic"]
    service._extractor = None
    service._classifier = None
    service._summarizer = None
    service._registry_facade = SimpleNamespace(
        resolve_bundle=lambda **kw: facade_calls.append(kw["session_id"]) or None,
        industry_bundle_map=lambda: {
            "bpo_contact_center": {"bundle_key": "ticketing", "aliases": []}
        },
    )
    service._llm_industry_classifier = SimpleNamespace(classify=fake_llm_classify)

    request = InterpreterRequest(
        session_id="s2", user_message="something unmappable", history=[]
    )
    _extracted, suggested = asyncio.run(service.interpret(request))

    assert facade_calls == ["s2"]
    assert llm_calls == ["s2"]
    assert suggested.selected_bundle is not None
    assert suggested.selected_bundle.bundle_key == "ticketing"
    assert suggested.confidence_status == "proceed"


def test_interpret_generic_fallback_when_both_stages_miss() -> None:
    """Stage 3: when alias AND LLM both return null, return generic fallback."""
    from agents.interpreter.llm_industry_classifier import IndustryChoice

    async def fake_llm_classify(**_kw: object) -> IndustryChoice:
        await asyncio.sleep(0)
        return IndustryChoice(
            industry=None, confidence=0.0, reasoning="No match"
        )

    service = object.__new__(InterpreterService)
    service._bundle_keys = ["generic"]
    service._extractor = None
    service._classifier = None
    service._summarizer = None
    service._registry_facade = SimpleNamespace(
        resolve_bundle=lambda **kw: None,
        industry_bundle_map=lambda: {},
    )
    service._llm_industry_classifier = SimpleNamespace(classify=fake_llm_classify)

    request = InterpreterRequest(
        session_id="s3", user_message="space robotics startup", history=[]
    )
    _extracted, suggested = asyncio.run(service.interpret(request))

    assert suggested.selected_bundle is not None
    assert suggested.selected_bundle.bundle_key == "generic"
    assert suggested.confidence_status == "fallback_generic"


def test_interpret_skips_llm_when_alias_resolver_hits() -> None:
    """Stage 1 short-circuits Stage 2 when the alias resolver finds a match."""
    from agents.interpreter.llm_industry_classifier import IndustryChoice

    llm_calls: list[str] = []

    async def fake_llm_classify(**kw: object) -> IndustryChoice:
        await asyncio.sleep(0)
        llm_calls.append("called")
        return IndustryChoice(industry=None, confidence=0.0, reasoning="")

    selected = BundleSuggestion(
        bundle_key="ticketing",
        display_name="Ticketing",
        confidence=0.95,
    )
    facade_result = ClassificationResult(
        session_id="s4",
        selected_bundle=selected,
        ranked_candidates=[selected],
        confidence_status="proceed",
        top_confidence=0.95,
    )

    service = object.__new__(InterpreterService)
    service._bundle_keys = ["ticketing"]
    service._extractor = None
    service._classifier = None
    service._summarizer = None
    service._registry_facade = SimpleNamespace(
        resolve_bundle=lambda **kw: facade_result,
        industry_bundle_map=lambda: {},
    )
    service._llm_industry_classifier = SimpleNamespace(classify=fake_llm_classify)

    request = InterpreterRequest(session_id="s4", user_message="bpo", history=[])
    _extracted, suggested = asyncio.run(service.interpret(request))

    assert llm_calls == []  # LLM stage NOT invoked
    assert suggested.selected_bundle is not None
    assert suggested.selected_bundle.bundle_key == "ticketing"
