from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from core.logging import get_logger
from domain.models.extracted_info import ExtractedInfo

from .prompts import EXTRACTION_SYSTEM_PROMPT

logger = get_logger(__name__)


class _ExtractionOutput(BaseModel):
    company_name: str | None = None
    industry_hint: str | None = None
    primary_use_case: str | None = None
    entity_type: str | None = None
    employee_names: list[str] = Field(default_factory=list)
    role_names: list[str] = Field(default_factory=list)
    department_names: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    status_labels: list[str] = Field(default_factory=list)


class Extractor:
    def __init__(self, model: ChatOpenAI) -> None:
        self._model = model

    async def extract(self, session_id: str, user_message: str) -> ExtractedInfo:
        structured = self._model.with_structured_output(_ExtractionOutput)
        try:
            result = await structured.ainvoke(
                [
                    SystemMessage(content=EXTRACTION_SYSTEM_PROMPT),
                    HumanMessage(content=user_message),
                ]
            )
        except (RuntimeError, ValueError, TypeError) as exc:
            logger.error("Extraction failed for session=%s: %s", session_id, exc)
            return ExtractedInfo(session_id=session_id)

        output = result if isinstance(result, _ExtractionOutput) else _ExtractionOutput.model_validate(result)
        return ExtractedInfo(
            session_id=session_id,
            company_name=output.company_name,
            industry_hint=output.industry_hint,
            primary_use_case=output.primary_use_case,
            entity_type=output.entity_type,
            employee_names=output.employee_names,
            role_names=output.role_names,
            department_names=output.department_names,
            metrics=output.metrics,
            status_labels=output.status_labels,
        )
