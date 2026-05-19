"""LLM-based industry classifier (Stage 2 of bundle resolution).

When the deterministic alias resolver in
``CanonicalBundleResolver._infer_industry`` fails to match, this classifier
asks the LLM to pick the best canonical industry from the
``industry_bundle_map`` aliases. The interpreter calls this only after the
deterministic stage misses, and falls back to the generic bundle if the LLM
also returns ``unknown`` or is not confident enough.
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from core.logging import get_logger
from domain.models.extraction_result import ExtractionResult

logger = get_logger(__name__)

_SYSTEM_PROMPT = (
    "You are routing a workspace onboarding request to the correct industry "
    "bundle. The candidate industries (with example aliases) are:\n\n"
    "{industry_block}\n\n"
    "Pick the single industry that best fits the user's request, or respond "
    "with industry=null if none of them is a reasonable match. Be honest "
    "about your confidence: low confidence is fine, do not invent fits."
)


class IndustryChoice(BaseModel):
    """Structured output from the LLM industry classifier."""

    industry: str | None = Field(
        ...,
        description=(
            "One of the candidate industry keys, or null if none match. "
            "Must exactly equal one of the listed industry keys."
        ),
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Self-reported confidence 0.0–1.0"
    )
    reasoning: str = Field(..., description="Brief justification, one sentence")


# pylint: disable=too-few-public-methods
class LLMIndustryClassifier:
    """Pick a canonical industry for an unmatched user message via LLM."""

    def __init__(
        self,
        model: ChatOpenAI,
        industry_map: dict[str, dict[str, Any]],
        min_confidence: float = 0.5,
    ) -> None:
        self._model = model
        self._industry_map = industry_map
        self._min_confidence = min_confidence

    async def classify(
        self,
        session_id: str,
        user_message: str,
        extracted: ExtractionResult | None = None,
    ) -> IndustryChoice:
        """Return the LLM's chosen industry, or industry=None if uncertain.

        Never raises: on LLM error, returns an ``IndustryChoice(None, 0.0)`` so
        the orchestrator can fall back to the generic bundle.
        """
        if not self._industry_map:
            return IndustryChoice(
                industry=None, confidence=0.0, reasoning="No industries configured"
            )

        industry_block = self._format_industries(self._industry_map)
        prompt = _SYSTEM_PROMPT.format(industry_block=industry_block)
        context = self._build_context(user_message, extracted)

        structured = self._model.with_structured_output(
            IndustryChoice, method="function_calling"
        )
        try:
            result = await structured.ainvoke(
                [
                    SystemMessage(content=prompt),
                    HumanMessage(content=context),
                ]
            )
        except (RuntimeError, ValueError, TypeError) as exc:
            logger.warning(
                "session=%s LLM industry classification failed: %s",
                session_id,
                exc,
            )
            return IndustryChoice(
                industry=None,
                confidence=0.0,
                reasoning=f"LLM error: {type(exc).__name__}",
            )

        choice = (
            result
            if isinstance(result, IndustryChoice)
            else IndustryChoice.model_validate(result)
        )

        if choice.industry is not None and choice.industry not in self._industry_map:
            logger.warning(
                "session=%s LLM returned unknown industry '%s'; treating as miss",
                session_id,
                choice.industry,
            )
            return IndustryChoice(
                industry=None,
                confidence=choice.confidence,
                reasoning=f"LLM chose unknown industry '{choice.industry}'",
            )

        if choice.industry is not None and choice.confidence < self._min_confidence:
            logger.info(
                "session=%s LLM industry '%s' below threshold (%.2f < %.2f)",
                session_id,
                choice.industry,
                choice.confidence,
                self._min_confidence,
            )
            return IndustryChoice(
                industry=None,
                confidence=choice.confidence,
                reasoning=(
                    f"Below confidence threshold ({choice.confidence:.2f}): "
                    f"{choice.reasoning}"
                ),
            )

        return choice

    @staticmethod
    def _format_industries(industry_map: dict[str, dict[str, Any]]) -> str:
        lines: list[str] = []
        for industry, spec in industry_map.items():
            aliases = spec.get("aliases", [])
            alias_text = ", ".join(str(a) for a in aliases) if aliases else "—"
            bundle_key = spec.get("bundle_key", "")
            lines.append(f"- {industry} (bundle={bundle_key}): {alias_text}")
        return "\n".join(lines)

    @staticmethod
    def _build_context(user_message: str, extracted: ExtractionResult | None) -> str:
        parts = [f"User request:\n{user_message}"]
        if extracted is None:
            return parts[0]

        cs = extracted.classification_signals
        signal_lines: list[str] = []
        if cs.intents:
            signal_lines.append(f"Intents: {', '.join(cs.intents)}")
        if cs.domain_hints:
            signal_lines.append(f"Domain hints: {', '.join(cs.domain_hints)}")
        if cs.keywords:
            signal_lines.append(f"Keywords: {', '.join(cs.keywords)}")
        if cs.workflow_hints:
            signal_lines.append(f"Workflow hints: {', '.join(cs.workflow_hints)}")
        if cs.entities:
            signal_lines.append(f"Entities: {', '.join(cs.entities)}")
        if signal_lines:
            parts.append("Extracted signals:\n" + "\n".join(signal_lines))
        return "\n\n".join(parts)
