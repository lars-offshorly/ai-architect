"""MockPayloadBuilder: assembles static mock payloads for frontend integration.

No AI pipeline, no LangGraph, no database. All data comes from:
  - Template files (app.json, dummy_data.json) via TemplateRepository
  - Feature flag registry (BUNDLE_REGISTRY / get_flag_snapshot)
  - docs/api-mocks.json loaded at construction time by the caller

Render keys vs template dirs:
  The router and frontend use render keys (hr_hub, project_mgmt, ticketing,
  generic). TemplateRepository uses template directory names (hr_hub,
  project_ops, field_service, generic). This class owns the translation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agents.app_generator.validators import validate_dummy_data_json
from agents.preview_generator.bundles.registry import (
    BUNDLE_REGISTRY,
    get_flag_snapshot,
)
from core.exceptions import InvalidPayloadError, TemplateLoadError
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
    ) -> None:
        self._repo = template_repo
        self._service_mocks: dict[str, Any] = service_mocks or {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build(
        self,
        bundle_key: str,
        dummy_data_override: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> MockPayload:
        """Assemble and return a complete MockPayload for the given render key.

        Args:
            bundle_key:           Render key (hr_hub, project_mgmt, ticketing, generic).
            dummy_data_override:  Caller-supplied dummy_data_json. When provided the
                                  template dummy_data.json file is skipped entirely.
                                  Accepts the full shape: bundle_key, session_id,
                                  company_name, stores.
            session_id:           Injected into dummy_data_json.session_id when the
                                  override does not already contain one.
        """
        template_dir = self._resolve_template_dir(bundle_key)

        generation_json = self._load_app_json(template_dir)

        if dummy_data_override is not None:
            validate_dummy_data_json(dummy_data_override, bundle_key)
            dummy_data_json = dummy_data_override
            # Inject session_id if caller supplied it and override omits it
            if session_id and not dummy_data_json.get("session_id"):
                dummy_data_json = {**dummy_data_json, "session_id": session_id}
            logger.info(
                "MockPayload built: bundle_key=%s template_dir=%s source=override",
                bundle_key,
                template_dir,
            )
        else:
            dummy_data_json = self._load_dummy_data(template_dir)
            if session_id and not dummy_data_json.get("session_id"):
                dummy_data_json = {**dummy_data_json, "session_id": session_id}
            logger.info(
                "MockPayload built: bundle_key=%s template_dir=%s source=template",
                bundle_key,
                template_dir,
            )

        flags, permission_services, landing_pages = self._resolve_flags(bundle_key)

        logger.info(
            "MockPayload flags: bundle_key=%s flags_enabled=%d",
            bundle_key,
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
        """Return only the template dummy_data_json (store seed data) for a bundle."""
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
            raise ValueError(f"Unknown render key: {bundle_key}")
        return RENDER_KEY_TO_TEMPLATE_DIR[bundle_key]

    def _load_app_json(self, template_dir: str) -> dict[str, Any]:
        try:
            return self._repo.load_app_json(template_dir)
        except TemplateLoadError as exc:
            logger.error("MockPayload: failed to load app.json for %s", template_dir)
            raise exc

    def _load_dummy_data(self, template_dir: str) -> dict[str, Any]:
        try:
            return self._repo.load_dummy_data(template_dir)
        except TemplateLoadError as exc:
            logger.error(
                "MockPayload: failed to load dummy_data.json for %s", template_dir
            )
            raise exc

    def _resolve_flags(
        self, bundle_key: str
    ) -> tuple[list[dict[str, Any]], list[str], list[dict[str, Any]]]:
        """Return feature flag snapshot and associated metadata for the bundle."""
        # 1. Map render key to registry bundle key
        # (This shim is temporary until Lars aligns the keys)
        registry_map = {
            "hr_hub": "hr_management",
            "project_mgmt": "project_mgmt",
            "ticketing": "ticketing",
            "generic": "generic",
        }
        registry_key = registry_map.get(bundle_key, "generic")

        # 2. Extract from BUNDLE_REGISTRY
        bundle = BUNDLE_REGISTRY.get(registry_key)
        if not bundle:
            return [], [], []

        # 3. Generate snapshots
        flags = get_flag_snapshot(registry_key)
        return flags, bundle.permission_services, bundle.landing_pages
