from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from catalog.bundle_catalog import BundleCatalog, BundleCatalogError
from core.exceptions import BundleRegistryValidationError


def _write_registry(tmp_path: Path, content: str) -> Path:
    registry = tmp_path / "registry.yaml"
    registry.write_text(textwrap.dedent(content), encoding="utf-8")
    return registry


_VALID_GENERIC_BUNDLE = """
  - bundle_key: generic
    display_name: Custom Workspace
    primary_entity: work
    description: Fallback bundle.
    template_dir: generic
    dummy_data_template_key: generic_base
    default_modules: [tickets]
    optional_modules: []
    knit_service_bundles: [ticketing]
    required_slots: [primary_use_case]
    synonyms: [custom]
    typical_entities: [work item]
    typical_intents: [general workflow]
    required_signals: []
    signal_boosts: {}
    terminology: {}
    metadata:
      kpis: []
      workflows: [general_request_handling]
      entity_definitions: {}
      onboarding_config_requirements: [primary_use_case]
      coverage: [general purpose workspace]
      settings_configurations: []
"""

_VALID_HR_BUNDLE = """
  - bundle_key: hr_management
    display_name: HR Management
    primary_entity: people
    description: HR bundle.
    template_dir: hr_management
    dummy_data_template_key: hr_management_base
    default_modules: [hr_hub]
    optional_modules: []
    knit_service_bundles: [hr_hub]
    required_slots: [team_size]
    synonyms: [human resources]
    typical_entities: [employee]
    typical_intents: [manage employees]
    required_signals: [employee workflow]
    signal_boosts:
      hr: 0.20
    terminology:
      primary_record_label: employee
    metadata:
      kpis: [active_headcount]
      workflows: [employee_onboarding]
      entity_definitions:
        employee:
          label: Employee
          plural: Employees
      onboarding_config_requirements: [leave_types]
      coverage: [employee reporting]
      settings_configurations: []
"""


class TestRegistryLoading:
    def test_loads_valid_registry(self, tmp_path: Path) -> None:
        content = "bundles:\n" + _VALID_HR_BUNDLE + _VALID_GENERIC_BUNDLE
        path = _write_registry(tmp_path, content)

        catalog = BundleCatalog(path)
        assert len(catalog.list_all()) == 2

    def test_raises_on_missing_file(self) -> None:
        with pytest.raises(BundleCatalogError, match="not found"):
            BundleCatalog(Path("nonexistent/registry.yaml"))

    def test_raises_on_invalid_yaml(self, tmp_path: Path) -> None:
        path = _write_registry(tmp_path, "bundles: [: invalid yaml :]")
        with pytest.raises(BundleCatalogError):
            BundleCatalog(path)

    def test_raises_on_missing_bundles_key(self, tmp_path: Path) -> None:
        path = _write_registry(tmp_path, "other_key: []")
        with pytest.raises(BundleCatalogError, match="top-level 'bundles'"):
            BundleCatalog(path)

    def test_raises_on_duplicate_bundle_key(self, tmp_path: Path) -> None:
        content = "bundles:\n" + _VALID_GENERIC_BUNDLE + _VALID_GENERIC_BUNDLE
        path = _write_registry(tmp_path, content)
        with pytest.raises(BundleCatalogError, match="Duplicate bundle_key"):
            BundleCatalog(path)


class TestRegistryValidation:
    def test_validate_passes_on_valid_registry(self, tmp_path: Path) -> None:
        content = "bundles:\n" + _VALID_HR_BUNDLE + _VALID_GENERIC_BUNDLE
        path = _write_registry(tmp_path, content)
        catalog = BundleCatalog(path)

        catalog.validate()

    def test_validate_fails_when_generic_missing(self, tmp_path: Path) -> None:
        content = "bundles:\n" + _VALID_HR_BUNDLE
        path = _write_registry(tmp_path, content)
        catalog = BundleCatalog(path)

        with pytest.raises(BundleRegistryValidationError, match="generic"):
            catalog.validate()

    def test_validate_fails_when_metadata_missing(self, tmp_path: Path) -> None:
        bundle_no_metadata = """
  - bundle_key: generic
    display_name: Custom Workspace
    primary_entity: work
    description: Fallback bundle.
    template_dir: generic
    dummy_data_template_key: generic_base
    default_modules: [tickets]
    optional_modules: []
    knit_service_bundles: [ticketing]
    required_slots: [primary_use_case]
    synonyms: [custom]
    typical_entities: [work item]
    typical_intents: [general workflow]
    required_signals: []
    signal_boosts: {}
    terminology: {}
"""
        content = "bundles:\n" + bundle_no_metadata
        path = _write_registry(tmp_path, content)
        catalog = BundleCatalog(path)

        with pytest.raises(BundleRegistryValidationError, match="metadata"):
            catalog.validate()

    def test_validate_fails_when_template_dir_empty(self, tmp_path: Path) -> None:
        bundle_empty_dir = """
  - bundle_key: generic
    display_name: Custom Workspace
    primary_entity: work
    description: Fallback bundle.
    template_dir: ''
    dummy_data_template_key: generic_base
    default_modules: [tickets]
    optional_modules: []
    knit_service_bundles: [ticketing]
    required_slots: [primary_use_case]
    synonyms: [custom]
    typical_entities: [work item]
    typical_intents: [general workflow]
    required_signals: []
    signal_boosts: {}
    terminology: {}
    metadata:
      kpis: []
      workflows: [general_request_handling]
      entity_definitions: {}
      onboarding_config_requirements: [primary_use_case]
      coverage: [general purpose workspace]
      settings_configurations: []
"""
        content = "bundles:\n" + bundle_empty_dir
        path = _write_registry(tmp_path, content)
        catalog = BundleCatalog(path)

        with pytest.raises(BundleRegistryValidationError, match="template_dir"):
            catalog.validate()

    def test_get_fallback_raises_when_generic_absent(self, tmp_path: Path) -> None:
        content = "bundles:\n" + _VALID_HR_BUNDLE
        path = _write_registry(tmp_path, content)
        catalog = BundleCatalog(path)

        with pytest.raises(BundleCatalogError, match="generic"):
            catalog.get_fallback()
