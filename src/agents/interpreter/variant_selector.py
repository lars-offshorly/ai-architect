"""Deterministic variant selector.

Scores each of a bundle's ``variants`` against the interpreter's extracted
signals and picks one. All logic is pure / rule-based — no LLM call.

Scoring
-------
::

    score(variant) =
        3 * |keywords         ∩ extracted.keywords|
      + 2 * |keywords         ∩ substring(user_message)|
      + 2 * |typical_entities ∩ extracted.entities|
      + 2 * |typical_intents  ∩ extracted.intents|
      + 1 * |industry_hints   ∩ extracted.domain_hints|
      − 4 * |anti_keywords    ∩ all_signals_concatenated|

A variant is chosen when ``top_score >= MIN_VARIANT_SCORE`` and the gap to
the runner-up is ``>= MIN_VARIANT_GAP``. Otherwise the selector returns
``None``, which callers should treat as a clarification trigger.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from catalog.bundle_catalog import BundleDefinition, BundleVariantDefinition
from core.constants import MIN_VARIANT_GAP, MIN_VARIANT_SCORE
from core.logging import get_logger
from domain.models.extraction_result import ExtractionResult

logger = get_logger(__name__)

_KW_WEIGHT = 3
_PHRASE_WEIGHT = 2
_ENTITY_WEIGHT = 2
_INTENT_WEIGHT = 2
_INDUSTRY_WEIGHT = 1
_ANTI_WEIGHT = 4


@dataclass
class VariantSelection:
    variant_key: str | None
    top_score: int
    score_gap: int
    ranked: list[tuple[str, int]] = field(default_factory=list)
    reason: str = ""


def select(
    bundle: BundleDefinition,
    extracted: ExtractionResult,
    user_message: str,
) -> VariantSelection:
    """Pick the best variant for *bundle*.

    Returns ``VariantSelection(variant_key=None, ...)`` when the bundle has
    no variants declared, when the top score is below ``MIN_VARIANT_SCORE``,
    or when the gap to the runner-up is below ``MIN_VARIANT_GAP``. The caller
    should then emit ``MissingFieldType.BUNDLE_VARIANT`` to trigger a
    clarification turn.
    """
    variants = bundle.variants
    if not variants:
        return VariantSelection(
            variant_key=None, top_score=0, score_gap=0, reason="no_variants"
        )

    cs = extracted.classification_signals
    signal_pool = _concatenate_signals(user_message, cs)
    extracted_keywords = _lower_set(cs.keywords)
    extracted_entities = _lower_set(cs.entities)
    extracted_intents = _lower_set(cs.intents)
    extracted_domains = _lower_set(cs.domain_hints)
    user_message_lower = user_message.lower()

    scored: list[tuple[BundleVariantDefinition, int]] = []
    for variant in variants:
        score = _score_variant(
            variant=variant,
            extracted_keywords=extracted_keywords,
            extracted_entities=extracted_entities,
            extracted_intents=extracted_intents,
            extracted_domains=extracted_domains,
            user_message_lower=user_message_lower,
            signal_pool=signal_pool,
        )
        scored.append((variant, score))

    scored.sort(key=lambda item: item[1], reverse=True)
    ranked = [(v.key, s) for v, s in scored]
    top_variant, top_score = scored[0]
    runner_up_score = scored[1][1] if len(scored) > 1 else 0
    gap = top_score - runner_up_score

    if top_score < MIN_VARIANT_SCORE:
        logger.info(
            "variant_selector: bundle=%s below_threshold top=%d gap=%d ranked=%s",
            bundle.bundle_key,
            top_score,
            gap,
            ranked,
        )
        return VariantSelection(
            variant_key=None,
            top_score=top_score,
            score_gap=gap,
            ranked=ranked,
            reason="below_threshold",
        )

    if gap < MIN_VARIANT_GAP:
        logger.info(
            "variant_selector: bundle=%s ambiguous_gap top=%d gap=%d ranked=%s",
            bundle.bundle_key,
            top_score,
            gap,
            ranked,
        )
        return VariantSelection(
            variant_key=None,
            top_score=top_score,
            score_gap=gap,
            ranked=ranked,
            reason="ambiguous_gap",
        )

    logger.info(
        "variant_selector: bundle=%s selected=%s top=%d gap=%d ranked=%s",
        bundle.bundle_key,
        top_variant.key,
        top_score,
        gap,
        ranked,
    )
    return VariantSelection(
        variant_key=top_variant.key,
        top_score=top_score,
        score_gap=gap,
        ranked=ranked,
        reason="selected",
    )


def _score_variant(
    *,
    variant: BundleVariantDefinition,
    extracted_keywords: set[str],
    extracted_entities: set[str],
    extracted_intents: set[str],
    extracted_domains: set[str],
    user_message_lower: str,
    signal_pool: str,
    # pylint: disable=too-many-arguments
) -> int:
    keyword_hits = _overlap_count(variant.keywords, extracted_keywords)
    phrase_hits = _phrase_match_count(variant.keywords, user_message_lower)
    entity_hits = _overlap_count(variant.typical_entities, extracted_entities)
    intent_hits = _overlap_count(variant.typical_intents, extracted_intents)
    industry_hits = _overlap_count(variant.industry_hints, extracted_domains)
    anti_hits = _phrase_match_count(variant.anti_keywords, signal_pool)

    return (
        _KW_WEIGHT * keyword_hits
        + _PHRASE_WEIGHT * phrase_hits
        + _ENTITY_WEIGHT * entity_hits
        + _INTENT_WEIGHT * intent_hits
        + _INDUSTRY_WEIGHT * industry_hits
        - _ANTI_WEIGHT * anti_hits
    )


def _overlap_count(needles: list[str], haystack: set[str]) -> int:
    if not needles or not haystack:
        return 0
    return sum(
        1
        for needle in needles
        if isinstance(needle, str) and needle.strip().lower() in haystack
    )


def _phrase_match_count(phrases: list[str], haystack: str) -> int:
    if not phrases or not haystack:
        return 0
    return sum(
        1
        for phrase in phrases
        if isinstance(phrase, str)
        and phrase.strip()
        and phrase.strip().lower() in haystack
    )


def _lower_set(values: list[str]) -> set[str]:
    return {value.strip().lower() for value in values if isinstance(value, str) and value.strip()}


def _concatenate_signals(user_message: str, cs) -> str:  # type: ignore[no-untyped-def]
    parts: list[str] = [user_message]
    parts.extend(cs.keywords)
    parts.extend(cs.entities)
    parts.extend(cs.intents)
    parts.extend(cs.workflow_hints)
    parts.extend(cs.domain_hints)
    parts.extend(cs.metrics)
    return " ".join(part for part in parts if isinstance(part, str)).lower()
