from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError


class BundleCatalogError(RuntimeError):
    pass


class BundleDefinition(BaseModel):
    bundle_key: str
    display_name: str
    primary_entity: str
    default_modules: list[str]
    required_slots: list[str]
    description: str
    optional_modules: list[str] = Field(default_factory=list)
    industry_hints: list[str] = Field(default_factory=list)
    dummy_data_template_key: str


class BundleCatalog:
    def __init__(self, catalog_path: Path | None = None) -> None:
        self._catalog_path = catalog_path or Path(__file__).with_name("bundles.json")
        self._bundles = self._load_bundles(self._catalog_path)

    @staticmethod
    def _load_bundles(catalog_path: Path) -> dict[str, BundleDefinition]:
        try:
            raw_payload = json.loads(catalog_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise BundleCatalogError(
                f"Bundle catalog file not found: {catalog_path}"
            ) from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise BundleCatalogError(
                f"Failed to read bundle catalog file: {catalog_path}"
            ) from exc

        if not isinstance(raw_payload, list):
            raise BundleCatalogError("Bundle catalog JSON must be a list of objects.")

        bundles: dict[str, BundleDefinition] = {}
        try:
            for item in raw_payload:
                bundle = BundleDefinition.model_validate(item)
                if bundle.bundle_key in bundles:
                    raise BundleCatalogError(
                        f"Duplicate bundle_key found: {bundle.bundle_key}"
                    )
                bundles[bundle.bundle_key] = bundle
        except ValidationError as exc:
            raise BundleCatalogError("Invalid bundle definition in catalog JSON.") from exc

        return bundles

    def get(self, bundle_key: str) -> BundleDefinition | None:
        return self._bundles.get(bundle_key)

    def list_keys(self) -> list[str]:
        return list(self._bundles.keys())

    def list_all(self) -> list[BundleDefinition]:
        return list(self._bundles.values())

    def match_by_entity(self, entity_type: str) -> list[BundleDefinition]:
        normalized_entity = entity_type.strip().casefold()
        if not normalized_entity:
            return []

        return [
            bundle
            for bundle in self._bundles.values()
            if bundle.primary_entity.casefold() == normalized_entity
        ]

    def match_by_industry_hint(self, hint: str) -> list[BundleDefinition]:
        normalized_hint = hint.strip().casefold()
        if not normalized_hint:
            return []

        matched_bundles: list[BundleDefinition] = []
        for bundle in self._bundles.values():
            for industry_hint in bundle.industry_hints:
                normalized_industry_hint = industry_hint.casefold()
                if (
                    normalized_hint in normalized_industry_hint
                    or normalized_industry_hint in normalized_hint
                ):
                    matched_bundles.append(bundle)
                    break

        return matched_bundles

    def get_required_slots(self, bundle_key: str) -> list[str]:
        bundle = self.get(bundle_key)
        if bundle is None:
            return []
        return list(bundle.required_slots)

    def get_fallback(self) -> BundleDefinition:
        fallback_bundle = self.get("generic")
        if fallback_bundle is None:
            raise BundleCatalogError("Catalog is missing required fallback bundle: generic")
        return fallback_bundle
