from __future__ import annotations

from pydantic import BaseModel, Field


class ExtractedInfo(BaseModel):
    """Adapter model that converts structured signals to slot format.

    This class serves as a bridge between the structured signal-based
    ExtractionResult and the flat slot format expected by downstream components.
    Rather than being deprecated, it provides a clean conversion layer that:

    1. Flattens ClassificationSignals (entities, workflow_hints) into single slots
    2. Extracts PersonalizationSignals into company_name, employee_names, etc.
    3. Preserves terminology mappings for template customization

    Use this when you need:
    - A flat key-value representation of extracted signals
    - Slots for downstream template injection
    - Backward compatibility with legacy slot-based interfaces

    For new code, prefer using ExtractionResult directly with its structured
    ClassificationSignals and PersonalizationSignals.

    See Also:
        ExtractionResult.to_extracted_info(): Method that creates this adapter
    """

    session_id: str
    company_name: str | None = None
    industry_hint: str | None = None
    primary_use_case: str | None = None
    entity_type: str | None = None
    employee_names: list[str] = Field(default_factory=list)
    role_names: list[str] = Field(default_factory=list)
    department_names: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    status_labels: list[str] = Field(default_factory=list)
    custom_terminology: dict[str, str] = Field(default_factory=dict)
    slots: dict[str, object] = Field(default_factory=dict)
