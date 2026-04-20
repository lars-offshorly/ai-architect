from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from catalog.bundle_catalog import BundleCatalog
from domain.models import BundleMetadata, EntityDefinition
from domain.services.bundle_metadata import BundleMetadataService

REGISTRY_PATH = (
    Path(__file__).resolve().parents[3] / "src/templates/bundle_registry.yaml"
)


@pytest.fixture(name="catalog")
def fixture_catalog(shared_catalog: BundleCatalog) -> BundleCatalog:
    return shared_catalog


@pytest.fixture(name="service")
def fixture_service(catalog: BundleCatalog) -> BundleMetadataService:
    return BundleMetadataService(catalog)


class TestBundleMetadataModel:
    def test_bundle_metadata_defaults(self) -> None:
        metadata = BundleMetadata(bundle_key="test")

        assert metadata.bundle_key == "test"
        assert metadata.kpis == []
        assert metadata.workflows == []
        assert metadata.entity_definitions == {}
        assert metadata.onboarding_config_requirements == []
        assert metadata.coverage == []
        assert metadata.settings_configurations == []

    def test_bundle_metadata_with_fields(self) -> None:
        metadata = BundleMetadata(
            bundle_key="hr_management",
            kpis=["active_headcount", "attendance_rate"],
            workflows=["employee_onboarding", "leave_request_and_approval"],
            entity_definitions={
                "employee": EntityDefinition(label="Employee", plural="Employees")
            },
            coverage=["employee reporting", "schedules"],
        )

        assert len(metadata.kpis) == 2
        assert len(metadata.workflows) == 2
        assert "employee" in metadata.entity_definitions
        assert metadata.entity_definitions["employee"].label == "Employee"
        assert metadata.entity_definitions["employee"].plural == "Employees"

    def test_entity_definition_fields(self) -> None:
        entity = EntityDefinition(label="Patient", plural="Patients")

        assert entity.label == "Patient"
        assert entity.plural == "Patients"


class TestBundleMetadataService:
    def test_get_metadata_returns_metadata_for_known_bundle(
        self, service: BundleMetadataService
    ) -> None:
        metadata = service.get_metadata("hr_management")

        assert metadata.bundle_key == "hr_management"
        assert len(metadata.kpis) > 0
        assert len(metadata.workflows) > 0

    def test_get_metadata_returns_empty_for_unknown_bundle(
        self, service: BundleMetadataService
    ) -> None:
        metadata = service.get_metadata("nonexistent_bundle")

        assert metadata.bundle_key == "nonexistent_bundle"
        assert metadata.kpis == []
        assert metadata.workflows == []

    def test_list_kpis_hr_management(self, service: BundleMetadataService) -> None:
        kpis = service.list_kpis("hr_management")

        assert "active_headcount" in kpis
        assert "attendance_rate" in kpis

    def test_list_kpis_legal_services(self, service: BundleMetadataService) -> None:
        kpis = service.list_kpis("legal_services")

        assert "avg_case_duration" in kpis
        assert "cases_per_attorney" in kpis

    def test_list_kpis_unknown_returns_empty(
        self, service: BundleMetadataService
    ) -> None:
        assert service.list_kpis("nonexistent") == []

    def test_list_workflows_project_mgmt(self, service: BundleMetadataService) -> None:
        workflows = service.list_workflows("project_mgmt")

        assert "project_creation" in workflows
        assert "task_assignment" in workflows

    def test_list_workflows_unknown_returns_empty(
        self, service: BundleMetadataService
    ) -> None:
        assert service.list_workflows("nonexistent") == []

    def test_list_coverage_healthcare(self, service: BundleMetadataService) -> None:
        coverage = service.list_coverage("healthcare")

        assert "patient intake" in coverage

    def test_list_onboarding_config_requirements_hr(
        self, service: BundleMetadataService
    ) -> None:
        requirements = service.list_onboarding_config_requirements("hr_management")

        assert "leave_types" in requirements
        assert "default_schedules" in requirements

    def test_list_settings_configurations_hr_management(
        self, service: BundleMetadataService
    ) -> None:
        configs = service.list_settings_configurations("hr_management")

        assert len(configs) > 0

    def test_service_uses_injected_catalog(self) -> None:
        mock_catalog = MagicMock(spec=BundleCatalog)
        mock_catalog.get_metadata.return_value = BundleMetadata(
            bundle_key="hr_management",
            kpis=["test_kpi"],
        )
        service = BundleMetadataService(mock_catalog)

        result = service.get_metadata("hr_management")

        mock_catalog.get_metadata.assert_called_once_with("hr_management")
        assert "test_kpi" in result.kpis

    def test_get_entity_definitions_returns_dict(
        self, service: BundleMetadataService
    ) -> None:
        defs = service.get_entity_definitions("hr_management")

        assert "employee" in defs
        assert defs["employee"].label == "Employee"

    def test_list_settings_configurations_unknown_returns_empty(
        self, service: BundleMetadataService
    ) -> None:
        assert service.list_settings_configurations("nonexistent") == []
