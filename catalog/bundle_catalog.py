from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, ValidationError

from core.config import get_settings
from core.exceptions import AppError, BundleRegistryValidationError
from domain.models.bundle_metadata import BundleMetadata, EntityDefinition


class BundleCatalogError(AppError):
    pass


class BundleDefinition(BaseModel):
    bundle_key: str
    render_key: str
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
    extraction_keywords: dict[str, Any] = Field(default_factory=dict)

    metadata: BundleMetadata | None = None


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
        include_legacy_aliases = catalog_path is None
        if catalog_path is None:
            try:
                catalog_path = Path(get_settings().BUNDLE_REGISTRY_PATH)
            except Exception:  # pylint: disable=broad-exception-caught
                catalog_path = Path("src/templates/bundle_registry.yaml")
        self._catalog_path = catalog_path
        self._bundles = self._load_bundles(self._catalog_path)
        if include_legacy_aliases:
            self._add_legacy_aliases()

    def _add_legacy_aliases(self) -> None:
        if "hr_hub" in self._bundles:
            return
        base = self._bundles.get("hr_management")
        if base is None:
            return
        self._bundles["hr_hub"] = BundleDefinition(
            bundle_key="hr_hub",
            display_name="HR Hub",
            primary_entity="people",
            description=base.description,
            template_dir=base.template_dir,
            dummy_data_template_key=base.dummy_data_template_key,
            default_modules=["tickets", "queues", "kpis", "dashboard"],
            optional_modules=list(base.optional_modules),
            knit_service_bundles=list(base.knit_service_bundles),
            required_slots=["team_size", "primary_use_case"],
            customizable_fields=list(base.customizable_fields),
            synonyms=list(base.synonyms),
            typical_entities=list(base.typical_entities),
            typical_intents=list(base.typical_intents),
            required_signals=list(base.required_signals),
            signal_boosts=dict(base.signal_boosts),
            terminology=dict(base.terminology),
            metadata=base.metadata,
        )

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

    def validate(self, templates_dir: Path | None = None) -> None:
        required_fields = (
            "bundle_key",
            "render_key",
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

            if templates_dir is not None:
                template_path = templates_dir / bundle.template_dir
                if not template_path.is_dir():
                    raise BundleRegistryValidationError(
                        f"Bundle '{bundle.bundle_key}' template directory does not "
                        f"exist: {template_path}"
                    )

            if bundle.bundle_key != "generic":
                if not bundle.typical_entities:
                    raise BundleRegistryValidationError(
                        f"Bundle '{bundle.bundle_key}' is missing required field "
                        f"'typical_entities'."
                    )
                if not bundle.typical_intents:
                    raise BundleRegistryValidationError(
                        f"Bundle '{bundle.bundle_key}' is missing required field "
                        f"'typical_intents'."
                    )
                if not bundle.required_signals:
                    raise BundleRegistryValidationError(
                        f"Bundle '{bundle.bundle_key}' is missing required field "
                        f"'required_signals'."
                    )

        if "generic" not in self._bundles:
            raise BundleRegistryValidationError(
                "Registry is missing required fallback bundle: generic"
            )

    def validate_template_consistency(self, templates_dir: Path) -> None:
        """Check overlap fields between registry and template JSON files.

        AD-2 precedence: registry owns display_name and modules for
        classification/orchestration. If a template JSON file declares these
        fields they must match the registry values to avoid silent divergence.
        """
        for bundle in self._bundles.values():
            bundle_dir = templates_dir / bundle.template_dir
            if not bundle_dir.is_dir():
                continue
            for json_file in bundle_dir.glob("*.json"):
                try:
                    data = json.loads(json_file.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                if not isinstance(data, dict):
                    continue

                if (
                    "display_name" in data
                    and data["display_name"] != bundle.display_name
                ):
                    raise BundleRegistryValidationError(
                        f"Bundle '{bundle.bundle_key}': "
                        f"template file '{json_file.name}' has display_name "
                        f"'{data['display_name']}' which conflicts with "
                        f"registry value '{bundle.display_name}'. "
                        f"Registry takes precedence (AD-2)."
                    )

                if "modules" in data:
                    template_modules = set(data["modules"])
                    registry_modules = set(bundle.default_modules)
                    if template_modules != registry_modules:
                        raise BundleRegistryValidationError(
                            f"Bundle '{bundle.bundle_key}': template file "
                            f"'{json_file.name}' has modules "
                            f"{sorted(template_modules)} which conflicts with "
                            f"registry default_modules {sorted(registry_modules)}. "
                            f"Registry takes precedence (AD-2)."
                        )

    def get(self, bundle_key: str) -> BundleDefinition | None:
        return self._bundles.get(bundle_key)

    def list_keys(self) -> list[str]:
        return list(self._bundles.keys())

    def list_all(self) -> list[BundleDefinition]:
        return list(self._bundles.values())

    def catalog_to_render_key(self) -> dict[str, str]:
        return {key: bundle.render_key for key, bundle in self._bundles.items()}

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
        """Match bundles by case-insensitive bidirectional substring on synonyms."""
        normalized = hint.strip().casefold()
        if not normalized:
            return []
        matched: list[BundleDefinition] = []
        for bundle in self._bundles.values():
            all_hints = bundle.synonyms
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

    def has_bundle(self, bundle_key: str) -> bool:
        return bundle_key in self._bundles

    def get_all_typical_intents(self) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for bundle in self._bundles.values():
            for intent in bundle.typical_intents:
                if intent not in seen:
                    seen.add(intent)
                    result.append(intent)
        return result

    def get_fallback(self) -> BundleDefinition:
        fallback_bundle = self.get("generic")
        if fallback_bundle is None:
            raise BundleCatalogError(
                "Catalog is missing required fallback bundle: generic"
            )
        return fallback_bundle


def _exported_key_sets() -> tuple[frozenset[str], frozenset[str]]:
    default_registry = (
        Path(__file__).resolve().parents[1] / "src/templates/bundle_registry.yaml"
    )
    try:
        catalog = BundleCatalog(default_registry)
    except BundleCatalogError:
        return frozenset(), frozenset()
    return frozenset(catalog.list_keys()), frozenset(
        catalog.catalog_to_render_key().values()
    )


CANONICAL_BUNDLE_KEYS, RENDER_KEYS = _exported_key_sets()
