"""MockPayloadBuilder: assembles mock payloads via the preview generator pipeline.

All data is produced by PreviewGeneratorService (the full LangGraph pipeline).
No static template files are loaded directly. The public interface (MockPayload,
MockPayloadBuilder.build / build_stores / build_flags, KNOWN_RENDER_KEYS) is
unchanged so the router and deps.py do not need to change.

Render keys:
  KNOWN_RENDER_KEYS is derived from the BundleCatalog at construction time, so
  it stays in sync with bundle_registry.yaml automatically.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from agents.app_generator.validators import validate_dummy_data_json
from agents.preview_generator.service import PreviewGeneratorService
from catalog.bundle_catalog import BundleCatalog
from core.logging import get_logger

logger = get_logger(__name__)


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
    """Assembles MockPayload objects by running the preview generator pipeline.

    Usage::

        builder = MockPayloadBuilder(
            preview_service=PreviewGeneratorService(catalog),
            catalog=catalog,
            service_mocks=api_mocks_dict,
        )
        payload = builder.build("hr_hub")
        stores  = builder.build_stores("hr_hub")
        flags   = builder.build_flags("hr_hub")
    """

    def __init__(
        self,
        preview_service: PreviewGeneratorService,
        catalog: BundleCatalog,
        service_mocks: dict[str, Any] | None = None,
    ) -> None:
        self._preview_service = preview_service
        self._catalog = catalog
        self._service_mocks: dict[str, Any] = service_mocks or {}
        self._known_render_keys: frozenset[str] = frozenset(
            b.render_key for b in catalog.list_all() if b.render_key
        )

    @property
    def known_render_keys(self) -> frozenset[str]:
        return self._known_render_keys

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

        Runs the preview generator pipeline to produce generation_json and
        dummy_data_json. When dummy_data_override is supplied, the pipeline
        still runs for generation_json but dummy_data_json is taken from the
        override instead.

        Args:
            bundle_key:           Render key (e.g. hr_hub, project_mgmt, ticketing).
            dummy_data_override:  Caller-supplied dummy_data_json. When provided the
                                  pipeline dummy data output is discarded.
                                  Accepted shape: bundle_key, session_id,
                                  company_name, stores.
            session_id:           Used as the pipeline session identifier.
                                  A UUID is generated when omitted.
        """
        self._validate_render_key(bundle_key)
        resolved_session_id = session_id or str(uuid.uuid4())

        catalog_key = self._resolve_catalog_key(bundle_key)
        generation_json, pipeline_dummy_data = self._preview_service.generate(
            session_id=resolved_session_id,
            bundle_key=catalog_key,
            conversation_history=[],
        )

        if dummy_data_override is not None:
            validate_dummy_data_json(dummy_data_override, bundle_key)
            dummy_data_json: dict[str, Any] = dummy_data_override
            if not dummy_data_json.get("session_id"):
                dummy_data_json = {**dummy_data_json, "session_id": resolved_session_id}
            logger.info(
                "MockPayload built: bundle_key=%s source=override session=%s",
                bundle_key,
                resolved_session_id,
            )
        else:
            dummy_data_json = pipeline_dummy_data
            logger.info(
                "MockPayload built: bundle_key=%s source=pipeline session=%s",
                bundle_key,
                resolved_session_id,
            )

        flags = generation_json.get("feature_flags", [])
        config = generation_json.get("config", {})
        permission_services: list[str] = config.get("permission_services", [])
        landing_pages: list[dict[str, Any]] = config.get("landing_pages", [])

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
        """Return dummy_data_json (store seed data) for a bundle via the pipeline."""
        self._validate_render_key(bundle_key)
        catalog_key = self._resolve_catalog_key(bundle_key)
        _, dummy_data_json = self._preview_service.generate(
            session_id=str(uuid.uuid4()),
            bundle_key=catalog_key,
            conversation_history=[],
        )
        logger.info("MockPayload stores built: bundle_key=%s", bundle_key)
        return dummy_data_json

    def build_flags(
        self, bundle_key: str
    ) -> tuple[list[dict[str, Any]], list[str], list[dict[str, Any]]]:
        """Return (feature_flags, permission_services, landing_pages) for render key."""
        self._validate_render_key(bundle_key)
        catalog_key = self._resolve_catalog_key(bundle_key)
        generation_json, _ = self._preview_service.generate(
            session_id=str(uuid.uuid4()),
            bundle_key=catalog_key,
            conversation_history=[],
        )
        flags: list[dict[str, Any]] = generation_json.get("feature_flags", [])
        config = generation_json.get("config", {})
        permission_services: list[str] = config.get("permission_services", [])
        landing_pages: list[dict[str, Any]] = config.get("landing_pages", [])
        logger.info(
            "MockPayload flags built: bundle_key=%s flags_enabled=%d",
            bundle_key,
            sum(1 for f in flags if f.get("isEnabled")),
        )
        return flags, permission_services, landing_pages

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _validate_render_key(self, bundle_key: str) -> None:
        if bundle_key not in self._known_render_keys:
            raise ValueError(f"Unknown render key: {bundle_key!r}")

    def _resolve_catalog_key(self, render_key: str) -> str:
        """Return the catalog bundle key that maps to the given render key."""
        for bundle in self._catalog.list_all():
            if bundle.render_key == render_key:
                return bundle.bundle_key
        return render_key


# ---------------------------------------------------------------------------
# Module-level KNOWN_RENDER_KEYS shim
# ---------------------------------------------------------------------------
# The router imports this name directly. It is populated by
# MockPayloadBuilder.__init__ at runtime; this sentinel keeps the import from
# failing before any builder is constructed.
KNOWN_RENDER_KEYS: frozenset[str] = frozenset()
