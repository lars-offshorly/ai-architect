from __future__ import annotations

from dataclasses import dataclass

from catalog.bundle_catalog import BundleCatalog
from domain.models.bundle_metadata import BundleMetadata
from domain.models.classification_result import ClassificationResult
from domain.models.extraction_result import ExtractionResult

from .canonical_bundle_resolver import CanonicalBundleResolver
from .canonical_metadata_service import CanonicalMetadataService
from .canonical_payload_builder import CanonicalPayloadBuilder


_DEFAULT_MODULES: dict[str, list[str]] = {
    "ticketing": ["tickets", "kpi", "dashboard"],
    "construction": ["projects", "kpi", "dashboard"],
    "hr_management": ["hr_hub", "tickets", "kpi", "dashboard"],
    "generic": ["tickets", "kpi", "dashboard"],
}
_CANONICAL_BASELINE_INTENTS: tuple[str, ...] = (
    "manage employees",
    "track attendance",
    "manage tickets",
    "manage projects",
)


@dataclass(slots=True)
class RegistryFacade:
    resolver: CanonicalBundleResolver
    payload_builder: CanonicalPayloadBuilder
    metadata_service: CanonicalMetadataService
    catalog_fallback: BundleCatalog | None = None
    allow_registry_module_fallback: bool = False

    def resolve_bundle(
        self,
        session_id: str,
        user_message: str,
        extracted: ExtractionResult | None = None,
    ) -> ClassificationResult:
        return self.resolver.resolve(session_id, user_message, extracted)

    def build_payload_stores(self, bundle_key: str, dummy_data_json: dict) -> bool:
        return self.payload_builder.apply_to_dummy_data(bundle_key, dummy_data_json)

    def get_bundle_metadata(self, bundle_key: str) -> BundleMetadata:
        return self.metadata_service.get_metadata(bundle_key)

    def list_supported_bundles(self) -> list[str]:
        return sorted(self.metadata_service.known_bundle_keys())

    def has_bundle(self, bundle_key: str) -> bool:
        return bundle_key in self.metadata_service.known_bundle_keys()

    def list_known_intents(self) -> list[str]:
        mapping = self.resolver.registry.industry_bundle_map()
        intents: list[str] = list(_CANONICAL_BASELINE_INTENTS)
        for industry, spec in mapping.items():
            intents.append(industry)
            aliases = spec.get("aliases", [])
            if isinstance(aliases, list):
                intents.extend([a for a in aliases if isinstance(a, str)])
        return sorted(set(intents))

    def inferred_modules_for_bundle(self, bundle_key: str) -> list[str]:
        if self.allow_registry_module_fallback and self.catalog_fallback is not None:
            bundle = self.catalog_fallback.get(bundle_key)
            if bundle is not None and bundle.default_modules:
                return list(bundle.default_modules)
        return list(_DEFAULT_MODULES.get(bundle_key, _DEFAULT_MODULES["generic"]))
