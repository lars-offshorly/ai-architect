from __future__ import annotations

from pydantic import BaseModel, Field


class ExtractedInfo(BaseModel):
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
