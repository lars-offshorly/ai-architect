from __future__ import annotations

from typing import Any

from domain.models.bundle_metadata import BundleMetadata, EntityDefinition

from .canonical_manifest_registry import CanonicalManifestRegistry


def _slug(label: str) -> str:
    return "_".join(label.strip().lower().replace("%", "pct").replace("/", " ").split())


class CanonicalMetadataService:
    def __init__(self, registry: CanonicalManifestRegistry) -> None:
        self._registry = registry

    def known_bundle_keys(self) -> set[str]:
        mapping = self._registry.industry_bundle_map()
        return {str(spec["bundle_key"]) for spec in mapping.values()} | {"generic"}

    def get_metadata(self, bundle_key: str) -> BundleMetadata:
        manifest = self._manifest_for_bundle(bundle_key)
        if manifest is None:
            return BundleMetadata(bundle_key=bundle_key)

        kpis = manifest.get("kpi", {}).get("kpis", [])
        request_types = manifest.get("hr_hub", {}).get("request_types", [])

        entity_definitions: dict[str, EntityDefinition] = {
            "employee": EntityDefinition(label="Employee", plural="Employees"),
            "queue": EntityDefinition(label="Queue", plural="Queues"),
            "project": EntityDefinition(label="Project", plural="Projects"),
            "kpi": EntityDefinition(label="KPI", plural="KPIs"),
        }

        workflows = ["tenant_provisioning"]
        if request_types:
            workflows.append("hr_request_handling")

        coverage = [manifest.get("tenant", {}).get("industry", "unknown_industry")]

        return BundleMetadata(
            bundle_key=bundle_key,
            kpis=[_slug(str(k.get("name", ""))) for k in kpis if isinstance(k, dict)],
            workflows=workflows,
            entity_definitions=entity_definitions,
            onboarding_config_requirements=["tenant.company_name", "tenant.industry"],
            coverage=coverage,
            settings_configurations=[],
        )

    def _manifest_for_bundle(self, bundle_key: str) -> dict[str, Any] | None:
        return self._registry.manifest_for_bundle(bundle_key)
