from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, ValidationError

from core.config import get_settings
from core.exceptions import AppError, BundleRegistryValidationError
from domain.models.bundle_metadata import BundleMetadata, EntityDefinition


class BundleCatalogError(AppError):
    pass


class BundleDefinition(BaseModel):
    bundle_key: str
    display_name: str
    primary_entity: str
    description: str
    template_dir: str
    dummy_data_template_key: str = ""

    default_modules: list[str] = Field(default_factory=list)
    optional_modules: list[str] = Field(default_factory=list)
    knit_service_bundles: list[str] = Field(default_factory=list)
    required_slots: list[str] = Field(default_factory=list)
    customizable_fields: list[str] = Field(default_factory=list)

    synonyms: list[str] = Field(default_factory=list)
    typical_entities: list[str] = Field(default_factory=list)
    typical_intents: list[str] = Field(default_factory=list)
    required_signals: list[str] = Field(default_factory=list)
    signal_boosts: dict[str, float] = Field(default_factory=dict)
    terminology: dict[str, str] = Field(default_factory=dict)

    metadata: BundleMetadata | None = None

    industry_hints: list[str] = Field(default_factory=list)


def _parse_metadata(bundle_key: str, raw: dict | None) -> BundleMetadata | None:
    if raw is None:
        return None
    entity_defs: dict[str, EntityDefinition] = {}
    for key, val in (raw.get("entity_definitions") or {}).items():
        if isinstance(val, dict):
            entity_defs[key] = EntityDefinition(
                label=str(val.get("label", key)),
                plural=str(val.get("plural", key + "s")),
            )
    return BundleMetadata(
        bundle_key=bundle_key,
        kpis=list(raw.get("kpis") or []),
        workflows=list(raw.get("workflows") or []),
        entity_definitions=entity_defs,
        onboarding_config_requirements=list(
            raw.get("onboarding_config_requirements") or []
        ),
        coverage=list(raw.get("coverage") or []),
        settings_configurations=list(raw.get("settings_configurations") or []),
    )


class BundleCatalog:
    def __init__(self, catalog_path: Path | None = None) -> None:
        if catalog_path is None:
            catalog_path = Path(get_settings().BUNDLE_REGISTRY_PATH)
        self._catalog_path = catalog_path
        self._bundles = self._load_bundles(self._catalog_path)

    @staticmethod
    def _load_bundles(catalog_path: Path) -> dict[str, BundleDefinition]:
        try:
            raw_text = catalog_path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise BundleCatalogError(
                f"Bundle registry file not found: {catalog_path}"
            ) from exc
        except OSError as exc:
            raise BundleCatalogError(
                f"Failed to read bundle registry file: {catalog_path}"
            ) from exc

        try:
            payload = yaml.safe_load(raw_text)
        except yaml.YAMLError as exc:
            raise BundleCatalogError(
                f"Failed to parse bundle registry YAML: {catalog_path}"
            ) from exc

        if not isinstance(payload, dict) or "bundles" not in payload:
            raise BundleCatalogError(
                "Bundle registry YAML must contain a top-level 'bundles' list."
            )

        raw_list = payload["bundles"]
        if not isinstance(raw_list, list):
            raise BundleCatalogError("'bundles' in registry YAML must be a list.")

        bundles: dict[str, BundleDefinition] = {}
        for item in raw_list:
            if not isinstance(item, dict):
                raise BundleCatalogError("Each bundle entry must be a YAML mapping.")
            bundle_key = str(item.get("bundle_key", ""))
            metadata = _parse_metadata(bundle_key, item.get("metadata"))
            try:
                bundle = BundleDefinition.model_validate({**item, "metadata": metadata})
            except ValidationError as exc:
                raise BundleCatalogError(
                    f"Invalid bundle definition for key '{bundle_key}'."
                ) from exc
            if bundle.bundle_key in bundles:
                raise BundleCatalogError(
                    f"Duplicate bundle_key found: {bundle.bundle_key}"
                )
            bundles[bundle.bundle_key] = bundle

        return bundles

    def validate(self) -> None:
        required_fields = (
            "bundle_key",
            "display_name",
            "primary_entity",
            "description",
            "template_dir",
        )

        for bundle in self._bundles.values():
            for field in required_fields:
                if not getattr(bundle, field, None):
                    raise BundleRegistryValidationError(
                        f"Bundle '{bundle.bundle_key}' is missing required field "
                        f"'{field}'."
                    )
            if bundle.metadata is None:
                raise BundleRegistryValidationError(
                    f"Bundle '{bundle.bundle_key}' is missing the metadata section."
                )

        if "generic" not in self._bundles:
            raise BundleRegistryValidationError(
                "Registry is missing required fallback bundle: generic"
            )

    def get(self, bundle_key: str) -> BundleDefinition | None:
        return self._bundles.get(bundle_key)

    def list_keys(self) -> list[str]:
        return list(self._bundles.keys())

    def list_all(self) -> list[BundleDefinition]:
        return list(self._bundles.values())

    def get_metadata(self, bundle_key: str) -> BundleMetadata | None:
        bundle = self.get(bundle_key)
        if bundle is None:
            return None
        return bundle.metadata

    def get_signal_boosts(self, bundle_key: str) -> dict[str, float]:
        bundle = self.get(bundle_key)
        if bundle is None:
            return {}
        return dict(bundle.signal_boosts)

    def match_by_entity(self, entity_type: str) -> list[BundleDefinition]:
        normalized = entity_type.strip().casefold()
        if not normalized:
            return []
        return [
            b
            for b in self._bundles.values()
            if b.primary_entity.casefold() == normalized
        ]

    def match_by_synonym(self, term: str) -> list[BundleDefinition]:
        normalized = term.strip().casefold()
        if not normalized:
            return []
        matched: list[BundleDefinition] = []
        for bundle in self._bundles.values():
            for synonym in bundle.synonyms:
                if normalized in synonym.casefold() or synonym.casefold() in normalized:
                    matched.append(bundle)
                    break
        return matched

    def match_by_typical_entity(self, entity: str) -> list[BundleDefinition]:
        normalized = entity.strip().casefold()
        if not normalized:
            return []
        matched: list[BundleDefinition] = []
        for bundle in self._bundles.values():
            for typical_entity in bundle.typical_entities:
                if (
                    normalized in typical_entity.casefold()
                    or typical_entity.casefold() in normalized
                ):
                    matched.append(bundle)
                    break
        return matched

    def match_by_industry_hint(self, hint: str) -> list[BundleDefinition]:
        normalized = hint.strip().casefold()
        if not normalized:
            return []
        matched: list[BundleDefinition] = []
        for bundle in self._bundles.values():
            all_hints = bundle.industry_hints + bundle.synonyms
            for h in all_hints:
                if normalized in h.casefold() or h.casefold() in normalized:
                    matched.append(bundle)
                    break
        return matched

    def get_required_slots(self, bundle_key: str) -> list[str]:
        bundle = self.get(bundle_key)
        if bundle is None:
            return []
        return list(bundle.required_slots)

    def get_fallback(self) -> BundleDefinition:
        fallback_bundle = self.get("generic")
        if fallback_bundle is None:
            raise BundleCatalogError(
                "Catalog is missing required fallback bundle: generic"
            )
        return fallback_bundle
