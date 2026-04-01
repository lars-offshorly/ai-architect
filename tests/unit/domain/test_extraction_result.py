from __future__ import annotations

# pylint: disable=no-member
from domain.enums.missing_field_type import MissingFieldType
from domain.models.extracted_info import ExtractedInfo
from domain.models.extraction_result import (
    ClassificationSignals,
    ExtractionResult,
    PersonalizationSignals,
)


class TestClassificationSignals:
    def test_defaults_are_empty(self) -> None:
        cs = ClassificationSignals()
        assert cs.keywords == []
        assert cs.entities == []
        assert cs.intents == []
        assert cs.workflow_hints == []
        assert cs.domain_hints == []
        assert cs.metrics == []

    def test_accepts_all_fields(self) -> None:
        cs = ClassificationSignals(
            keywords=["hr", "leave"],
            entities=["employee"],
            intents=["approve"],
            workflow_hints=["leave approval"],
            domain_hints=["healthcare"],
            metrics=["headcount"],
        )
        assert cs.keywords == ["hr", "leave"]
        assert cs.entities == ["employee"]
        assert cs.metrics == ["headcount"]


class TestPersonalizationSignals:
    def test_defaults_are_empty(self) -> None:
        ps = PersonalizationSignals()
        assert ps.company_name is None
        assert ps.employee_names == []
        assert ps.role_names == []
        assert ps.department_names == []
        assert ps.branch_names == []
        assert ps.custom_labels == []
        assert ps.terminology == {}

    def test_accepts_all_fields(self) -> None:
        ps = PersonalizationSignals(
            company_name="Acme Corp",
            employee_names=["Jane Smith"],
            role_names=["HR Manager"],
            department_names=["HR"],
            terminology={"leave_request": "time-off form"},
        )
        assert ps.company_name == "Acme Corp"
        assert ps.role_names == ["HR Manager"]
        assert ps.terminology["leave_request"] == "time-off form"


class TestExtractionResult:
    def test_defaults(self) -> None:
        result = ExtractionResult(session_id="s1")
        assert result.session_id == "s1"
        assert result.classification_signals.keywords == []
        assert result.personalization_signals.company_name is None
        assert result.missing_fields == []

    def test_accepts_nested_signals(self) -> None:
        result = ExtractionResult(
            session_id="s1",
            classification_signals=ClassificationSignals(
                keywords=["employee", "leave"],
                entities=["employee"],
                intents=["request leave"],
            ),
            personalization_signals=PersonalizationSignals(
                company_name="Acme",
                employee_names=["Bob"],
            ),
            missing_fields=[MissingFieldType.TEAM_SIZE],
        )
        assert result.classification_signals.keywords == ["employee", "leave"]
        assert result.personalization_signals.company_name == "Acme"
        assert MissingFieldType.TEAM_SIZE in result.missing_fields


class TestToExtractedInfo:
    def test_returns_extracted_info(self) -> None:
        result = ExtractionResult(session_id="s1")
        info = result.to_extracted_info()
        assert isinstance(info, ExtractedInfo)
        assert info.session_id == "s1"

    def test_maps_personalization_fields(self) -> None:
        result = ExtractionResult(
            session_id="s1",
            personalization_signals=PersonalizationSignals(
                company_name="Acme",
                employee_names=["Jane"],
                role_names=["Manager"],
                department_names=["HR"],
            ),
        )
        info = result.to_extracted_info()
        assert info.company_name == "Acme"
        assert info.employee_names == ["Jane"]
        assert info.role_names == ["Manager"]
        assert info.department_names == ["HR"]

    def test_maps_classification_fields(self) -> None:
        result = ExtractionResult(
            session_id="s1",
            classification_signals=ClassificationSignals(
                domain_hints=["healthcare"],
                workflow_hints=["patient management"],
                entities=["patient"],
                metrics=["avg_wait_time"],
            ),
        )
        info = result.to_extracted_info()
        assert info.industry_hint == "healthcare"
        assert info.primary_use_case == "patient management"
        assert info.entity_type == "patient"
        assert "avg_wait_time" in info.metrics

    def test_slots_dict_populated_from_personalization(self) -> None:
        result = ExtractionResult(
            session_id="s1",
            personalization_signals=PersonalizationSignals(company_name="Acme"),
            classification_signals=ClassificationSignals(
                workflow_hints=["leave management"],
                entities=["employee"],
            ),
        )
        info = result.to_extracted_info()
        assert info.slots["company_name"] == "Acme"
        assert info.slots["primary_use_case"] == "leave management"
        assert info.slots["entity_type"] == "employee"

    def test_empty_classification_fields_map_to_none(self) -> None:
        result = ExtractionResult(session_id="s1")
        info = result.to_extracted_info()
        assert info.industry_hint is None
        assert info.primary_use_case is None
        assert info.entity_type is None

    def test_extracted_info_is_frozen_no_new_fields(self) -> None:
        """ExtractedInfo must not grow new fields — AD-1 contract."""
        expected_fields = {
            "session_id",
            "company_name",
            "industry_hint",
            "primary_use_case",
            "entity_type",
            "employee_names",
            "role_names",
            "department_names",
            "metrics",
            "status_labels",
            "custom_terminology",
            "slots",
        }
        assert set(ExtractedInfo.model_fields.keys()) == expected_fields
