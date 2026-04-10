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
        """Return only the dummy_data_json stores for the given render key."""
        template_dir = self._resolve_template_dir(bundle_key)
        dummy_data_json = self._load_dummy_data(template_dir)
        logger.info("MockPayload stores built: bundle_key=%s", bundle_key)
        return dummy_data_json

    def build_flags(self, bundle_key: str) -> tuple[list[dict[str, Any]], list[str], list[dict[str, Any]]]:
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
        registry_entry = BUNDLE_REGISTRY.get(bundle_key, {})
        enabled_names: set[str] = set(registry_entry.get("flags", []))

        for addon_key in registry_entry.get("compatible_addons", []):
            addon = BUNDLE_REGISTRY.get(addon_key, {})
            enabled_names.update(addon.get("flags", []))

        snapshot = get_flag_snapshot()
        for flag in snapshot:
            if flag["name"] in enabled_names:
                flag["isEnabled"] = True

        return (
            snapshot,
            registry_entry.get("permission_services", []),
            registry_entry.get("landing_pages", []),
        )
