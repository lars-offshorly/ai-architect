"""Unit tests for agents.interpreter.variant_selector."""

from __future__ import annotations

import pytest

from agents.interpreter.variant_selector import select
from catalog.bundle_catalog import BundleDefinition, BundleVariantDefinition
from domain.models.extraction_result import (
    ClassificationSignals,
    ExtractionResult,
    PersonalizationSignals,
)


def _variant(
    key: str,
    *,
    is_default: bool = False,
    keywords: list[str] | None = None,
    anti_keywords: list[str] | None = None,
    typical_entities: list[str] | None = None,
    typical_intents: list[str] | None = None,
    industry_hints: list[str] | None = None,
) -> BundleVariantDefinition:
    return BundleVariantDefinition(
        key=key,
        display_name=key,
        description="",
        is_default=is_default,
        keywords=keywords or [],
        anti_keywords=anti_keywords or [],
        typical_entities=typical_entities or [],
        typical_intents=typical_intents or [],
        industry_hints=industry_hints or [],
    )


def _bundle(variants: list[BundleVariantDefinition]) -> BundleDefinition:
    return BundleDefinition(
        bundle_key="demo",
        display_name="Demo",
        primary_entity="thing",
        description="",
        render_key="demo",
        template_dir="demo",
        variants=variants,
    )


def _extracted(
    *,
    keywords: list[str] | None = None,
    entities: list[str] | None = None,
    intents: list[str] | None = None,
    domain_hints: list[str] | None = None,
) -> ExtractionResult:
    return ExtractionResult(
        session_id="s1",
        classification_signals=ClassificationSignals(
            keywords=keywords or [],
            entities=entities or [],
            intents=intents or [],
            domain_hints=domain_hints or [],
        ),
        personalization_signals=PersonalizationSignals(),
    )


def test_no_variants_returns_none_and_reason():
    bundle = _bundle([])
    result = select(bundle, _extracted(), "anything")
    assert result.variant_key is None
    assert result.reason == "no_variants"


def test_clear_winner_by_keyword_overlap():
    bundle = _bundle(
        [
            _variant("app-01", is_default=True, keywords=["hospital", "inpatient"]),
            _variant("app-02", keywords=["clinic", "outpatient"]),
            _variant("app-03", keywords=["pharma", "clinical trial"]),
        ]
    )
    result = select(bundle, _extracted(keywords=["hospital", "inpatient"]), "")
    assert result.variant_key == "app-01"
    assert result.reason == "selected"


def test_phrase_hits_from_user_message():
    bundle = _bundle(
        [
            _variant("app-01", is_default=True, keywords=["hospital"]),
            _variant("app-02", keywords=["clinic", "outpatient"]),
        ]
    )
    result = select(
        bundle,
        _extracted(),
        "we run an outpatient clinic with appointments and referrals",
    )
    assert result.variant_key == "app-02"


def test_tie_below_threshold_triggers_clarification():
    bundle = _bundle(
        [
            _variant("app-01", is_default=True, keywords=["hospital"]),
            _variant("app-02", keywords=["clinic"]),
        ]
    )
    # Both keywords appear exactly once → tie, gap=0 → below MIN_VARIANT_SCORE.
    result = select(bundle, _extracted(), "hospital and clinic both relevant")
    assert result.variant_key is None
    assert result.reason == "below_threshold"


def test_below_threshold_triggers_clarification():
    bundle = _bundle(
        [
            _variant("app-01", is_default=True, keywords=["hospital"]),
            _variant("app-02", keywords=["clinic"]),
        ]
    )
    # Unrelated message → zero signal.
    result = select(bundle, _extracted(), "track something generic please")
    assert result.variant_key is None
    assert result.reason == "below_threshold"


def test_anti_keywords_penalise_mismatch():
    """Anti-keywords should push a wrongly-matching variant below its rival."""
    bundle = _bundle(
        [
            _variant(
                "app-01",
                is_default=True,
                keywords=["general"],
                anti_keywords=["pharma"],
            ),
            _variant("app-02", keywords=["pharma"]),
        ]
    )
    # "general pharma" hits app-01 once (keyword) but also triggers its anti.
    result = select(bundle, _extracted(keywords=["pharma"]), "general pharma request")
    assert result.variant_key == "app-02"


def test_industry_hint_contributes_to_score():
    bundle = _bundle(
        [
            _variant(
                "app-01",
                is_default=True,
                keywords=["generic"],
                industry_hints=["healthcare"],
            ),
            _variant("app-02", keywords=["other"]),
        ]
    )
    result = select(
        bundle,
        _extracted(keywords=["generic"], domain_hints=["healthcare"]),
        "",
    )
    assert result.variant_key == "app-01"
