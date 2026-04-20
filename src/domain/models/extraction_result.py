from __future__ import annotations

# pylint: disable=no-member,duplicate-code
from pydantic import BaseModel, Field

from domain.enums.missing_field_type import MissingFieldType
from domain.models.extracted_info import ExtractedInfo


class ClassificationSignals(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    intents: list[str] = Field(default_factory=list)
    workflow_hints: list[str] = Field(default_factory=list)
    domain_hints: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)


class PersonalizationSignals(BaseModel):
    company_name: str | None = None
    employee_names: list[str] = Field(default_factory=list)
    role_names: list[str] = Field(default_factory=list)
    department_names: list[str] = Field(default_factory=list)
    branch_names: list[str] = Field(default_factory=list)
    custom_labels: list[str] = Field(default_factory=list)
    terminology: dict[str, str] = Field(default_factory=dict)


class ExtractionResult(BaseModel):
    session_id: str
    classification_signals: ClassificationSignals = Field(
        default_factory=ClassificationSignals
    )
    personalization_signals: PersonalizationSignals = Field(
        default_factory=PersonalizationSignals
    )
    missing_fields: list[MissingFieldType] = Field(default_factory=list)
    bundle_variant_key: str | None = None

    def to_extracted_info(self) -> ExtractedInfo:
        cs = self.classification_signals
        ps = self.personalization_signals

        slots: dict[str, object] = {}
        if ps.company_name:
            slots["company_name"] = ps.company_name
        if cs.workflow_hints:
            slots["primary_use_case"] = cs.workflow_hints[0]
        if cs.entities:
            slots["entity_type"] = cs.entities[0]
        if self.bundle_variant_key:
            slots["bundle_variant_key"] = self.bundle_variant_key

        return ExtractedInfo(
            session_id=self.session_id,
            company_name=ps.company_name,
            industry_hint=cs.domain_hints[0] if cs.domain_hints else None,
            primary_use_case=cs.workflow_hints[0] if cs.workflow_hints else None,
            entity_type=cs.entities[0] if cs.entities else None,
            bundle_variant_key=self.bundle_variant_key,
            employee_names=ps.employee_names,
            role_names=ps.role_names,
            department_names=ps.department_names,
            metrics=cs.metrics,
            custom_terminology=ps.terminology,
            slots=slots,
        )
