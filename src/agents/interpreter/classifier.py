from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from core.logging import get_logger
from domain.models.bundle import BundleSuggestion, SuggestedBundles
from domain.services.bundle_resolution import BundleResolutionService

from .prompts import CLASSIFICATION_SYSTEM_PROMPT
from .rules import apply_rule_boosts, build_signal_boosts, detect_signals

logger = get_logger(__name__)


class _BundleScore(BaseModel):
    bundle_key: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""
    matched_signals: list[str] = Field(default_factory=list)


class _ClassificationOutput(BaseModel):
    scores: list[_BundleScore] = Field(default_factory=list)


class Classifier:
    def __init__(self, model: ChatOpenAI, catalog_context: str) -> None:
        self._model = model
        self._catalog_context = catalog_context
        self._resolver = BundleResolutionService()

    async def classify(
        self,
        session_id: str,
        user_message: str,
        bundle_keys: list[str],
    ) -> SuggestedBundles:
        prompt = CLASSIFICATION_SYSTEM_PROMPT.format(catalog_context=self._catalog_context)
        structured = self._model.with_structured_output(_ClassificationOutput)
        try:
            result = await structured.ainvoke(
                [
                    SystemMessage(content=prompt),
                    HumanMessage(content=user_message),
                ]
            )
        except (RuntimeError, ValueError, TypeError) as exc:
            logger.error("Classification failed for session=%s: %s", session_id, exc)
            return SuggestedBundles(session_id=session_id)

        output = (
            result
            if isinstance(result, _ClassificationOutput)
            else _ClassificationOutput.model_validate(result)
        )
        candidates = [
            {
                "bundle_key": s.bundle_key,
                "display_name": s.bundle_key,
                "confidence": s.confidence,
                "reasoning": s.reasoning,
                "matched_signals": s.matched_signals,
            }
            for s in output.scores
            if s.bundle_key in bundle_keys
        ]
        signals = detect_signals(user_message)
        boosts = build_signal_boosts()
        boosted = apply_rule_boosts(candidates, boosts, signals)
        return self._resolver.rank(session_id, boosted)

    def top_suggestion(self, suggested: SuggestedBundles, threshold: float) -> BundleSuggestion | None:
        top = suggested.top()
        if top is None or top.confidence < threshold:
            return None
        return top
