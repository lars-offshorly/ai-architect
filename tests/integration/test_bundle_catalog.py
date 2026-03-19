from __future__ import annotations

import pytest

from catalog.bundle_catalog import BundleCatalog


@pytest.fixture(name="catalog")
def fixture_catalog() -> BundleCatalog:
    return BundleCatalog()


def test_loads_all_bundles(catalog: BundleCatalog) -> None:
    assert len(catalog.list_all()) >= 4


def test_get_hr_hub_returns_correct_data(catalog: BundleCatalog) -> None:
    hr_hub = catalog.get("hr_hub")

    assert hr_hub is not None
    assert hr_hub.display_name == "HR Hub"
    assert hr_hub.primary_entity == "people"
    assert "tickets" in hr_hub.default_modules


def test_get_nonexistent_returns_none(catalog: BundleCatalog) -> None:
    assert catalog.get("nonexistent") is None


def test_match_by_entity_includes_hr_hub(catalog: BundleCatalog) -> None:
    matches = catalog.match_by_entity("people")
    assert any(bundle.bundle_key == "hr_hub" for bundle in matches)


def test_match_by_industry_hint_includes_hr_hub(catalog: BundleCatalog) -> None:
    matches = catalog.match_by_industry_hint("tech")
    assert any(bundle.bundle_key == "hr_hub" for bundle in matches)


def test_get_required_slots_includes_team_size(catalog: BundleCatalog) -> None:
    required_slots = catalog.get_required_slots("hr_hub")
    assert "team_size" in required_slots


def test_get_fallback_returns_generic(catalog: BundleCatalog) -> None:
    fallback_bundle = catalog.get_fallback()
    assert fallback_bundle.bundle_key == "generic"
