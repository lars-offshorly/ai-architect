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
