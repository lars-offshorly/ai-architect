from __future__ import annotations

from pydantic import BaseModel, Field


class BundleSuggestionSchema(BaseModel):
    bundle_key: str
    display_name: str
    confidence: float
    reasoning: str = ""


class InterpreterResultSchema(BaseModel):
    session_id: str
    top_bundle_key: str | None = None
    suggestions: list[BundleSuggestionSchema] = Field(default_factory=list)
    extracted_company_name: str | None = None
    extracted_entity_type: str | None = None
    extracted_primary_use_case: str | None = None
    slots: dict[str, object] = Field(default_factory=dict)
