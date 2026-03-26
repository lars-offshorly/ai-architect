from __future__ import annotations

from catalog.bundle_catalog import BundleCatalog
from domain.models.bundle_metadata import BundleMetadata


class BundleMetadataService:
    def __init__(self, catalog: BundleCatalog) -> None:
        self._catalog = catalog

    def get_metadata(self, bundle_key: str) -> BundleMetadata:
        metadata = self._catalog.get_metadata(bundle_key)
        if metadata is None:
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
