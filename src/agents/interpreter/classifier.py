"""Legacy bundle classifier — evaluation/non-runtime only.

The canonical runtime path resolves bundles via ``RegistryFacade`` against
``new_json_samples/*.jsonc``. This module is kept for offline evaluation
harnesses and legacy unit tests that still exercise catalog-based ranking.
Do not wire it into runtime dependencies.
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from catalog.bundle_catalog import BundleCatalog, BundleDefinition
from core.logging import get_logger
from domain.models.bundle import BundleSuggestion
from domain.models.classification_result import ClassificationResult
from domain.models.extraction_result import ExtractionResult

from .prompts import CLASSIFICATION_SYSTEM_PROMPT
from .rules import apply_rule_boosts, detect_signals

logger = get_logger(__name__)

_INTENT_BOOST = 0.15


def _apply_intent_boost(
    candidates: list[dict[str, object]],
    bundles: list[BundleDefinition],
    intent: str,
) -> list[dict[str, object]]:
    bundle_map = {b.bundle_key: b for b in bundles}
    for candidate in candidates:
        bundle = bundle_map.get(str(candidate.get("bundle_key", "")))
        if bundle and any(intent in ti.lower() for ti in bundle.typical_intents):
            candidate["confidence"] = min(
                1.0,
                _to_float(candidate.get("confidence", 0.0)) + _INTENT_BOOST,
            )
    return candidates


class _BundleScore(BaseModel):
    bundle_key: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""
    matched_signals: list[str] = Field(default_factory=list)


class _ClassificationOutput(BaseModel):
    scores: list[_BundleScore] = Field(default_factory=list)


# pylint: disable=too-few-public-methods
class Classifier:
    def __init__(
        self, model: ChatOpenAI, catalog_context: str, catalog: BundleCatalog
    ) -> None:
        self._model = model
        self._catalog_context = catalog_context
        self._catalog = catalog
        self._bundle_map = {bundle.bundle_key: bundle for bundle in catalog.list_all()}

    async def classify(
        self,
        session_id: str,
        user_message: str,
        bundle_keys: list[str],
        extracted: ExtractionResult | None = None,
        preselected_intent: str | None = None,
        # Signature follows interpreter contract for Week 3 pipeline.
        # pylint: disable=too-many-arguments
        # pylint: disable=too-many-positional-arguments,too-many-locals
    ) -> ClassificationResult:
        prompt = CLASSIFICATION_SYSTEM_PROMPT.format(
            catalog_context=self._catalog_context
        )
        structured = self._model.with_structured_output(
            _ClassificationOutput, method="function_calling"
        )
        try:
            result = await structured.ainvoke(
                [
                    SystemMessage(content=prompt),
                    HumanMessage(content=user_message),
                ]
            )
        except (RuntimeError, ValueError, TypeError) as exc:
            logger.error("Classification failed for session=%s: %s", session_id, exc)
            return ClassificationResult(
                session_id=session_id,
                confidence_status="clarify",
                reasoning="Classifier failed",
            )

        output = (
            result
            if isinstance(result, _ClassificationOutput)
            else _ClassificationOutput.model_validate(result)
        )
        candidates: list[dict[str, object]] = []
        for score in output.scores:
            if score.bundle_key not in bundle_keys:
                continue
            bundle = self._bundle_map.get(score.bundle_key)
            candidates.append(
                {
                    "bundle_key": score.bundle_key,
                    "display_name": (
                        bundle.display_name if bundle is not None else score.bundle_key
                    ),
                    "confidence": score.confidence,
                    "reasoning": score.reasoning,
                    "matched_signals": score.matched_signals,
                }
            )

        bundles = [
            self._bundle_map[key] for key in bundle_keys if key in self._bundle_map
        ]
        signals = _detect_context_signals(user_message, extracted, preselected_intent)
        detected = detect_signals(signals, bundles)
        boosted = apply_rule_boosts(candidates, bundles, detected)
        if preselected_intent:
            boosted = _apply_intent_boost(boosted, bundles, preselected_intent.lower())
        ranked_candidates = _to_ranked_candidates(boosted)
        top = ranked_candidates[0] if ranked_candidates else None
        top_confidence = top.confidence if top is not None else 0.0
        second_confidence = (
            ranked_candidates[1].confidence if len(ranked_candidates) > 1 else 0.0
        )
        score_gap = (
            top_confidence - second_confidence
            if len(ranked_candidates) > 1
            else top_confidence
        )
        return ClassificationResult(
            session_id=session_id,
            selected_bundle=top,
            ranked_candidates=ranked_candidates,
            confidence_status="clarify",
            top_confidence=top_confidence,
            score_gap=score_gap,
            reasoning="LLM + registry signal boosts",
        )


def _detect_context_signals(
    user_message: str,
    extracted: ExtractionResult | None,
    preselected_intent: str | None,
) -> list[str]:
    signals = [user_message]
    if preselected_intent:
        signals.append(preselected_intent)
    if extracted is None:
        return signals
    cs = extracted.classification_signals
    signals.extend(cs.keywords)
    signals.extend(cs.entities)
    signals.extend(cs.intents)
    signals.extend(cs.workflow_hints)
    signals.extend(cs.domain_hints)
    signals.extend(cs.metrics)
    return signals


def _to_ranked_candidates(
    candidates: list[dict[str, object]],
) -> list[BundleSuggestion]:
    ranked = [
        BundleSuggestion(
            bundle_key=str(candidate["bundle_key"]),
            display_name=str(candidate.get("display_name", candidate["bundle_key"])),
            confidence=max(0.0, min(1.0, _to_float(candidate.get("confidence", 0.0)))),
            reasoning=str(candidate.get("reasoning", "")),
            matched_signals=_to_str_list(candidate.get("matched_signals", [])),
        )
        for candidate in candidates
    ]
    ranked.sort(key=lambda item: item.confidence, reverse=True)
    return ranked


def _to_float(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return 0.0
    return 0.0


def _to_str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]
