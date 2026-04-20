from __future__ import annotations

import inspect
from types import SimpleNamespace

from agents.interpreter.service import InterpreterService
from catalog.bundle_catalog import BundleDefinition, BundleVariantDefinition
from domain.enums.missing_field_type import MissingFieldType
from domain.models.bundle import BundleSuggestion
from domain.models.classification_result import ClassificationResult
from domain.models.extraction_result import ExtractionResult


def test_interpret_returns_extraction_result_type() -> None:
    """InterpreterService.interpret() must return ExtractionResult."""

    sig = inspect.signature(InterpreterService.interpret)
    # Return annotation should reference ExtractionResult
    hints = sig.return_annotation
    assert "ExtractionResult" in str(hints)


def test_apply_variant_selection_sets_variant_key(monkeypatch) -> None:
    service = object.__new__(InterpreterService)
    service._catalog = SimpleNamespace(
        get=lambda _bundle_key: BundleDefinition(
            bundle_key="hr_hub",
            display_name="HR Hub",
            primary_entity="people",
            description="",
            render_key="hr_hub",
            template_dir="hr_hub",
            variants=[
                BundleVariantDefinition(
                    key="app-01",
                    display_name="General HR",
                    description="",
                    is_default=True,
                )
            ],
        )
    )

    extracted = ExtractionResult(session_id="s1")
    suggested = ClassificationResult(
        session_id="s1",
        selected_bundle=BundleSuggestion(
            bundle_key="hr_hub",
            display_name="HR Hub",
            confidence=0.9,
        ),
    )

    class _Selection:
        variant_key = "app-01"
        top_score = 6
        score_gap = 3
        reason = "selected"

    monkeypatch.setattr(
        "agents.interpreter.service.select_variant",
        lambda **_kwargs: _Selection(),
    )

    service._apply_variant_selection("s1", "general hr workspace", extracted, suggested)

    assert extracted.bundle_variant_key == "app-01"
    assert suggested.selected_bundle is not None
    assert suggested.selected_bundle.variant_key == "app-01"
    assert suggested.selected_bundle.variant_confidence == 0.667


def test_apply_variant_selection_marks_clarification_needed(monkeypatch) -> None:
    service = object.__new__(InterpreterService)
    service._catalog = SimpleNamespace(
        get=lambda _bundle_key: BundleDefinition(
            bundle_key="hr_hub",
            display_name="HR Hub",
            primary_entity="people",
            description="",
            render_key="hr_hub",
            template_dir="hr_hub",
            variants=[
                BundleVariantDefinition(
                    key="app-01",
                    display_name="General HR",
                    description="",
                    is_default=True,
                )
            ],
        )
    )

    extracted = ExtractionResult(session_id="s1")
    suggested = ClassificationResult(
        session_id="s1",
        selected_bundle=BundleSuggestion(
            bundle_key="hr_hub",
            display_name="HR Hub",
            confidence=0.9,
        ),
    )

    class _Selection:
        variant_key = None
        top_score = 1
        score_gap = 0
        reason = "below_threshold"

    monkeypatch.setattr(
        "agents.interpreter.service.select_variant",
        lambda **_kwargs: _Selection(),
    )

    service._apply_variant_selection("s1", "general hr workspace", extracted, suggested)

    assert extracted.bundle_variant_key is None
    assert MissingFieldType.BUNDLE_VARIANT in extracted.missing_fields
