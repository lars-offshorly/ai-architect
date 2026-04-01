from __future__ import annotations

from pathlib import Path

import pytest

from catalog.bundle_catalog import BundleCatalog, BundleCatalogError

REGISTRY_PATH = (
    Path(__file__).resolve().parents[2] / "src/templates/bundle_registry.yaml"
)
EXPECTED_BUNDLE_COUNT = 12


@pytest.fixture(name="catalog")
def fixture_catalog() -> BundleCatalog:
    return BundleCatalog(REGISTRY_PATH)


def test_loads_all_twelve_bundles(catalog: BundleCatalog) -> None:
    assert len(catalog.list_all()) == EXPECTED_BUNDLE_COUNT


def test_all_expected_bundle_keys_present(catalog: BundleCatalog) -> None:
    expected = {
        "hr_management",
        "ticketing",
        "project_mgmt",
        "finance",
        "marketing",
        "sales",
        "healthcare",
        "legal_services",
        "construction_real_estate",
        "education",
        "all_microservices",
        "generic",
    }
    assert expected == set(catalog.list_keys())


def test_get_hr_management_returns_correct_data(catalog: BundleCatalog) -> None:
    bundle = catalog.get("hr_management")

    assert bundle is not None
    assert bundle.display_name == "HR Management"
    assert bundle.primary_entity == "people"
    assert "hr_hub" in bundle.default_modules
    assert "hr_hub" in bundle.knit_service_bundles


def test_get_ticketing_returns_correct_data(catalog: BundleCatalog) -> None:
    bundle = catalog.get("ticketing")

    assert bundle is not None
    assert bundle.display_name == "Ticketing Tool"
    assert bundle.primary_entity == "ticket"
    assert "ticketing" in bundle.knit_service_bundles


def test_get_project_mgmt_returns_correct_data(catalog: BundleCatalog) -> None:
    bundle = catalog.get("project_mgmt")

    assert bundle is not None
    assert bundle.display_name == "Project Management"
    assert bundle.primary_entity == "project"
    assert "project_mgmt" in bundle.knit_service_bundles


def test_get_nonexistent_returns_none(catalog: BundleCatalog) -> None:
    assert catalog.get("nonexistent") is None


def test_get_fallback_returns_generic(catalog: BundleCatalog) -> None:
    fallback = catalog.get_fallback()
    assert fallback.bundle_key == "generic"


def test_match_by_entity_people(catalog: BundleCatalog) -> None:
    matches = catalog.match_by_entity("people")
    assert any(b.bundle_key == "hr_management" for b in matches)


def test_match_by_entity_ticket(catalog: BundleCatalog) -> None:
    matches = catalog.match_by_entity("ticket")
    assert any(b.bundle_key == "ticketing" for b in matches)


def test_match_by_entity_case(catalog: BundleCatalog) -> None:
    matches = catalog.match_by_entity("case")
    assert any(b.bundle_key == "legal_services" for b in matches)


def test_match_by_synonym_hr(catalog: BundleCatalog) -> None:
    matches = catalog.match_by_synonym("human resources")
    assert any(b.bundle_key == "hr_management" for b in matches)


def test_match_by_synonym_crm(catalog: BundleCatalog) -> None:
    matches = catalog.match_by_synonym("CRM")
    assert any(b.bundle_key == "sales" for b in matches)


def test_match_by_synonym_lms(catalog: BundleCatalog) -> None:
    matches = catalog.match_by_synonym("LMS")
    assert any(b.bundle_key == "education" for b in matches)


def test_match_by_typical_entity_patient(catalog: BundleCatalog) -> None:
    matches = catalog.match_by_typical_entity("patient")
    assert any(b.bundle_key == "healthcare" for b in matches)


def test_match_by_typical_entity_attorney(catalog: BundleCatalog) -> None:
    matches = catalog.match_by_typical_entity("attorney")
    assert any(b.bundle_key == "legal_services" for b in matches)


def test_match_by_industry_hint_falls_back_to_synonyms(catalog: BundleCatalog) -> None:
    matches = catalog.match_by_industry_hint("e-learning")
    assert any(b.bundle_key == "education" for b in matches)


def test_get_required_slots_hr_management(catalog: BundleCatalog) -> None:
    slots = catalog.get_required_slots("hr_management")
    assert "team_size" in slots
    assert "primary_use_case" in slots


def test_get_required_slots_nonexistent_returns_empty(catalog: BundleCatalog) -> None:
    assert catalog.get_required_slots("nonexistent") == []


def test_get_signal_boosts_hr_management(catalog: BundleCatalog) -> None:
    boosts = catalog.get_signal_boosts("hr_management")
    assert "hr" in boosts
    assert boosts["hr"] > 0.0


def test_get_signal_boosts_legal_services(catalog: BundleCatalog) -> None:
    boosts = catalog.get_signal_boosts("legal_services")
    assert "attorney" in boosts
    assert boosts["attorney"] > 0.0


def test_get_signal_boosts_nonexistent_returns_empty(catalog: BundleCatalog) -> None:
    assert catalog.get_signal_boosts("nonexistent") == {}


def test_get_metadata_hr_management(catalog: BundleCatalog) -> None:
    metadata = catalog.get_metadata("hr_management")

    assert metadata is not None
    assert metadata.bundle_key == "hr_management"
    assert "active_headcount" in metadata.kpis
    assert "employee_onboarding" in metadata.workflows
    assert "employee" in metadata.entity_definitions


def test_get_metadata_legal_services(catalog: BundleCatalog) -> None:
    metadata = catalog.get_metadata("legal_services")

    assert metadata is not None
    assert "avg_case_duration" in metadata.kpis
    assert "case_intake" in metadata.workflows


def test_get_metadata_nonexistent_returns_none(catalog: BundleCatalog) -> None:
    assert catalog.get_metadata("nonexistent") is None


def test_every_bundle_has_metadata(catalog: BundleCatalog) -> None:
    for bundle in catalog.list_all():
        assert (
            bundle.metadata is not None
        ), f"Bundle '{bundle.bundle_key}' has no metadata"


def test_every_bundle_has_knit_service_bundles(catalog: BundleCatalog) -> None:
    for bundle in catalog.list_all():
        assert (
            bundle.knit_service_bundles
        ), f"Bundle '{bundle.bundle_key}' has empty knit_service_bundles"


def test_validate_passes_on_valid_registry(catalog: BundleCatalog) -> None:
    catalog.validate()


def test_catalog_errors_on_missing_file() -> None:
    with pytest.raises(BundleCatalogError):
        BundleCatalog(Path("nonexistent/path.yaml"))


def test_validate_with_template_dirs_passes(
    catalog: BundleCatalog, tmp_path: Path
) -> None:
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()
    for bundle in catalog.list_all():
        (templates_dir / bundle.template_dir).mkdir(exist_ok=True)

    catalog.validate(templates_dir=templates_dir)
