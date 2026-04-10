"""MockPayloadBuilder: assembles static mock payloads for frontend integration.

No AI pipeline, no LangGraph, no database. All data comes from:
  - Template files (app.json, dummy_data.json) via TemplateRepository
  - BundleCatalog (bundle_registry.yaml + feature_flags.yaml)
  - docs/api-mocks.json loaded at construction time by the caller

Render keys vs template dirs:
  The router and frontend use render keys (hr_hub, project_mgmt, ticketing,
  generic). TemplateRepository uses template directory names (hr_hub,
  project_ops, field_service, generic). This class owns the translation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from catalog.bundle_catalog import BundleCatalog
from core.exceptions import TemplateLoadError
from core.logging import get_logger
from repositories.template_repository import TemplateRepository

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Render key → template directory
# Update when Lars exposes render_key from BundleCatalog / bundle_registry.yaml
# ---------------------------------------------------------------------------

RENDER_KEY_TO_TEMPLATE_DIR: dict[str, str] = {
    "hr_hub": "hr_hub",
    "project_mgmt": "project_ops",
    "ticketing": "field_service",
    "generic": "generic",
}

RENDER_KEY_TO_CATALOG_KEY: dict[str, str] = {
    "hr_hub": "hr_management",
    "project_mgmt": "project_mgmt",
    "ticketing": "ticketing",
    "generic": "generic",
}

KNOWN_RENDER_KEYS: frozenset[str] = frozenset(RENDER_KEY_TO_TEMPLATE_DIR)


# ---------------------------------------------------------------------------
# Output model
# ---------------------------------------------------------------------------


@dataclass
class MockPayload:
    """Assembled mock payload returned by MockPayloadBuilder."""

    bundle_key: str
    generation_json: dict[str, Any]
    dummy_data_json: dict[str, Any]
    feature_flags: list[dict[str, Any]]
    permission_services: list[str]
    landing_pages: list[dict[str, Any]]
    service_mocks: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


class MockPayloadBuilder:
    """Assembles MockPayload objects from templates, registry, and api-mocks.json.

    Usage::

        builder = MockPayloadBuilder(
            template_repo=TemplateRepository(),
            service_mocks=api_mocks_dict,
        )
        payload = builder.build("hr_hub")
        stores  = builder.build_stores("hr_hub")
        flags   = builder.build_flags("hr_hub")
    """

    def __init__(
        self,
        template_repo: TemplateRepository,
        service_mocks: dict[str, Any] | None = None,
        catalog: BundleCatalog | None = None,
    ) -> None:
        self._repo = template_repo
        self._service_mocks: dict[str, Any] = service_mocks or {}
        self._catalog = catalog or BundleCatalog()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build(self, bundle_key: str) -> MockPayload:
        """Assemble and return a complete MockPayload for the given render key."""
        template_dir = self._resolve_template_dir(bundle_key)

        generation_json = self._load_app_json(template_dir)
        dummy_data_json = self._load_dummy_data(template_dir)
        flags, permission_services, landing_pages = self._resolve_flags(bundle_key)

        logger.info(
            "MockPayload built: bundle_key=%s template_dir=%s flags_enabled=%d",
            bundle_key,
            template_dir,
            sum(1 for f in flags if f.get("isEnabled")),
        )

        return MockPayload(
            bundle_key=bundle_key,
            generation_json=generation_json,
            dummy_data_json=dummy_data_json,
            feature_flags=flags,
            permission_services=permission_services,
            landing_pages=landing_pages,
            service_mocks=self._service_mocks,
        )

    def build_stores(self, bundle_key: str) -> dict[str, Any]:
        """Return only the dummy_data_json stores for the given render key."""
        template_dir = self._resolve_template_dir(bundle_key)
        dummy_data_json = self._load_dummy_data(template_dir)
        logger.info("MockPayload stores built: bundle_key=%s", bundle_key)
        return dummy_data_json

    def build_flags(
        self, bundle_key: str
    ) -> tuple[list[dict[str, Any]], list[str], list[dict[str, Any]]]:
        """Return (feature_flags, permission_services, landing_pages) for render key."""
        self._resolve_template_dir(bundle_key)  # validates key
        flags, permission_services, landing_pages = self._resolve_flags(bundle_key)
        logger.info(
            "MockPayload flags built: bundle_key=%s flags_enabled=%d",
            bundle_key,
            sum(1 for f in flags if f.get("isEnabled")),
        )
        return flags, permission_services, landing_pages

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _resolve_template_dir(self, bundle_key: str) -> str:
        """Translate render key to template dir, raising ValueError for unknown keys."""
        if bundle_key not in KNOWN_RENDER_KEYS:
            raise ValueError(
                f"Unknown render key '{bundle_key}'. "
                f"Valid keys: {sorted(KNOWN_RENDER_KEYS)}"
            )
        return RENDER_KEY_TO_TEMPLATE_DIR[bundle_key]

    def _load_app_json(self, template_dir: str) -> dict[str, Any]:
        try:
            return self._repo.load_app_json(template_dir)
        except TemplateLoadError as exc:
            raise TemplateLoadError(template_dir, f"app.json: {exc}") from exc

    def _load_dummy_data(self, template_dir: str) -> dict[str, Any]:
        try:
            return self._repo.load_dummy_data(template_dir)
        except TemplateLoadError as exc:
            raise TemplateLoadError(template_dir, f"dummy_data.json: {exc}") from exc

    def _resolve_flags(
        self, bundle_key: str
    ) -> tuple[list[dict[str, Any]], list[str], list[dict[str, Any]]]:
        """Build flag snapshot with bundle + compatible addon flags enabled."""
        catalog_key = RENDER_KEY_TO_CATALOG_KEY.get(bundle_key, bundle_key)
        bundle = self._catalog.get(catalog_key)
        if bundle is None:
            return self._catalog.get_feature_flags(), [], []

        enabled_names: set[str] = set(bundle.flags)
        for addon_key in bundle.compatible_addons:
            addon = self._catalog.get(addon_key)
            if addon is not None:
                enabled_names.update(addon.flags)

        snapshot = self._catalog.get_feature_flags()
        for flag in snapshot:
            if flag["name"] in enabled_names:
                flag["isEnabled"] = True

        return (
            snapshot,
            list(bundle.permission_services),
            list(bundle.landing_pages),
        )
