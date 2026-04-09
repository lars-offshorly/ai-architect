from __future__ import annotations

# pylint: disable=too-few-public-methods,duplicate-code
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from catalog.bundle_catalog import BundleCatalog, BundleDefinition
from core.logging import get_logger
from domain.models.conversation import ConversationMessage
from domain.models.extraction_result import (
    ClassificationSignals,
    ExtractionResult,
    PersonalizationSignals,
)

from .prompts import EXTRACTION_SYSTEM_PROMPT

logger = get_logger(__name__)

_HISTORY_WINDOW = 5


def _build_extraction_context(
    user_message: str,
    summary: str,
    history: list[ConversationMessage],
) -> str:
    parts: list[str] = []
    if summary:
        parts.append(f"Conversation summary:\n{summary}")
    recent = history[-_HISTORY_WINDOW:]
    if recent:
        lines = []
        for msg in recent:
            prefix = "User" if msg.role == "user" else "Assistant"
            lines.append(f"{prefix}: {msg.content}")
        parts.append("Recent conversation:\n" + "\n".join(lines))
    parts.append(f"Latest message:\n{user_message}")
    return "\n\n".join(parts)


def _build_synonym_index(
    bundles: list[BundleDefinition],
) -> tuple[dict[str, str], list[tuple[str, str]]]:
    exact_match_index: dict[str, str] = {}
    phrase_match_index: list[tuple[str, str]] = []

    for bundle in bundles:
        for synonym in bundle.synonyms:
            normalized = synonym.strip().casefold()
            if not normalized:
                continue
            if normalized not in exact_match_index:
                exact_match_index[normalized] = synonym
                phrase_match_index.append((normalized, synonym))

    phrase_match_index.sort(key=lambda item: len(item[0]), reverse=True)
    return exact_match_index, phrase_match_index


def _normalize_keywords(
    keywords: list[str],
    exact_match_index: dict[str, str],
    phrase_match_index: list[tuple[str, str]],
) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()

    for kw in keywords:
        stripped = kw.strip()
        if not stripped:
            continue

        normalized = stripped.casefold()
        canonical = exact_match_index.get(normalized)
        if canonical is None:
            for phrase, mapped in phrase_match_index:
                if phrase in normalized or normalized in phrase:
                    canonical = mapped
                    break
        if canonical is None:
            canonical = stripped

        canonical_key = canonical.casefold()
        if canonical_key in seen:
            continue
        result.append(canonical)
        seen.add(canonical_key)
    return result


class _ClassificationSignalsOutput(BaseModel):
    # For OpenAI Structured Outputs, every field must be required in the schema.
    # We remove default_factory and use ... to mark as required.
    keywords: list[str] = Field(..., description="Keywords extracted from text")
    entities: list[str] = Field(..., description="Entity types identified")
    intents: list[str] = Field(..., description="User business intents")
    workflow_hints: list[str] = Field(..., description="Specific workflow hints")
    domain_hints: list[str] = Field(..., description="Business domain hints")
    metrics: list[str] = Field(..., description="Metrics or KPIs mentioned")


class _PersonalizationSignalsOutput(BaseModel):
    company_name: str | None = Field(..., description="Company name if mentioned")
    employee_names: list[str] = Field(..., description="Names of employees")
    role_names: list[str] = Field(..., description="Job role names")
    department_names: list[str] = Field(..., description="Department names")
    branch_names: list[str] = Field(..., description="Office branch names")
    custom_labels: list[str] = Field(..., description="Other custom labels")
    terminology: dict[str, str] = Field(..., description="Custom terminology mapping")


class _ExtractionOutput(BaseModel):
    classification_signals: _ClassificationSignalsOutput = Field(
        ..., description="Signals used for bundle classification"
    )
    personalization_signals: _PersonalizationSignalsOutput = Field(
        ..., description="Signals used for workspace personalization"
    )


class Extractor:
    def __init__(self, model: ChatOpenAI, catalog: BundleCatalog) -> None:
        self._model = model
        self._catalog = catalog
        self._bundles = catalog.list_all()
        self._exact_synonym_index, self._phrase_synonym_index = _build_synonym_index(
            self._bundles
        )

    async def extract(
        self,
        session_id: str,
        user_message: str,
        history: list[ConversationMessage] | None = None,
        summary: str = "",
    ) -> ExtractionResult:
        context = _build_extraction_context(
            user_message=user_message,
            summary=summary,
            history=history or [],
        )
        # Use method="function_calling" if schema issues persist, but first try
        # making the Pydantic schema strictly required.
        structured = self._model.with_structured_output(_ExtractionOutput)
        try:
            result = await structured.ainvoke(
                [
                    SystemMessage(content=EXTRACTION_SYSTEM_PROMPT),
                    HumanMessage(content=context),
                ]
            )
        except (RuntimeError, ValueError, TypeError) as exc:
            logger.error("Extraction failed for session=%s: %s", session_id, exc)
            return ExtractionResult(session_id=session_id)

        output = (
            result
            if isinstance(result, _ExtractionOutput)
            else _ExtractionOutput.model_validate(result)
        )
        normalized_keywords = _normalize_keywords(
            output.classification_signals.keywords,
            self._exact_synonym_index,
            self._phrase_synonym_index,
        )
        cs = output.classification_signals
        ps = output.personalization_signals
        return ExtractionResult(
            session_id=session_id,
            classification_signals=ClassificationSignals(
                keywords=normalized_keywords,
                entities=cs.entities,
                intents=cs.intents,
                workflow_hints=cs.workflow_hints,
                domain_hints=cs.domain_hints,
                metrics=cs.metrics,
            ),
            personalization_signals=PersonalizationSignals(
                company_name=ps.company_name,
                employee_names=ps.employee_names,
                role_names=ps.role_names,
                department_names=ps.department_names,
                branch_names=ps.branch_names,
                custom_labels=ps.custom_labels,
                terminology=ps.terminology,
            ),
        )
