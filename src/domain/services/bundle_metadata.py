from __future__ import annotations

import logging

from catalog.bundle_catalog import BundleCatalog
from domain.models.bundle_metadata import BundleMetadata, EntityDefinition

logger = logging.getLogger(__name__)


class BundleMetadataService:
    """Deprecated runtime path (registry-yaml based metadata service).

    Canonical runtime entrypoints now use CanonicalMetadataService via
    RegistryFacade. This service remains for compatibility with legacy tests.
    """

    def __init__(self, catalog: BundleCatalog) -> None:
        self._catalog = catalog

    def get_metadata(self, bundle_key: str) -> BundleMetadata:
        metadata = self._catalog.get_metadata(bundle_key)
        if metadata is None:
            logger.warning("get_metadata called for unknown bundle_key=%s", bundle_key)
            return BundleMetadata(bundle_key=bundle_key)
        return metadata

    def list_kpis(self, bundle_key: str) -> list[str]:
        return self.get_metadata(bundle_key).kpis

    def list_workflows(self, bundle_key: str) -> list[str]:
        return self.get_metadata(bundle_key).workflows

    def list_coverage(self, bundle_key: str) -> list[str]:
        return self.get_metadata(bundle_key).coverage

    def list_onboarding_config_requirements(self, bundle_key: str) -> list[str]:
        return self.get_metadata(bundle_key).onboarding_config_requirements

    def list_settings_configurations(self, bundle_key: str) -> list[str]:
        return self.get_metadata(bundle_key).settings_configurations

    def get_entity_definitions(self, bundle_key: str) -> dict[str, EntityDefinition]:
        return self.get_metadata(bundle_key).entity_definitions
