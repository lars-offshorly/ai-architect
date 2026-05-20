from __future__ import annotations

from typing import Any

from .canonical_manifest_registry import CanonicalManifestRegistry


def _slug(label: str) -> str:
    return "_".join(label.strip().lower().replace("%", "pct").replace("/", " ").split())


class CanonicalPayloadBuilder:
    """Builds dummy_data stores from canonical tenant provisioning manifests."""

    def __init__(self, registry: CanonicalManifestRegistry) -> None:
        self._registry = registry

    def apply_to_dummy_data(
        self, bundle_key: str, dummy_data_json: dict[str, Any]
    ) -> bool:
        manifest = self._manifest_for_bundle(bundle_key)
        if manifest is None:
            return False

        stores = dummy_data_json.setdefault("stores", {})

        queues = manifest.get("tickets", {}).get("queues", [])
        stores["queues"] = [
            {"id": q.get("id"), "name": q.get("name"), "ticket_count": 0}
            for q in queues
            if isinstance(q, dict)
        ]

        projects = manifest.get("projects", {}).get("projects", [])
        stores["projects"] = [
            {"id": p.get("id"), "name": p.get("name"), "status": "planned"}
            for p in projects
            if isinstance(p, dict)
        ]

        if not stores.get("kpis"):
            kpis = manifest.get("kpi", {}).get("kpis", [])
            stores["kpis"] = [
                {
                    "id": k.get("id"),
                    "key": _slug(str(k.get("name", ""))),
                    "label": k.get("name"),
                    "value": 0,
                    "unit": "count",
                    "trend": "stable",
                }
                for k in kpis
                if isinstance(k, dict)
            ]

        employees = manifest.get("hr_hub", {}).get("employees", [])
        stores["employees"] = [e for e in employees if isinstance(e, dict)]

        request_types = manifest.get("hr_hub", {}).get("request_types", [])
        stores["request_types"] = [r for r in request_types if isinstance(r, dict)]

        dashboards = manifest.get("dashboard", {}).get("dashboards", [])
        stores["canonical_dashboards"] = [d for d in dashboards if isinstance(d, dict)]
        return True

    def _manifest_for_bundle(self, bundle_key: str) -> dict[str, Any] | None:
        by_industry = self._registry.by_industry()
        mapping = self._registry.industry_bundle_map()
        for industry, payload in by_industry.items():
            spec = mapping.get(industry, {})
            if spec.get("bundle_key") == bundle_key:
                return payload
        return None
