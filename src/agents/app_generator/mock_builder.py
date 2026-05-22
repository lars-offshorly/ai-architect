"""MockPayloadBuilder: assembles mock payloads for frontend integration.

Mock payloads must be shaped like real preview payloads.

Implementation:
- Uses the production `PreviewFlow` to ensure the response includes:
  - static bundle template overlay (`app-0*.json` operational stores)
  - static dashboard output injection (`dashboard_output_templates/*`)

The public interface (MockPayload, MockPayloadBuilder.build / build_stores /
build_flags, KNOWN_RENDER_KEYS) remains stable for the router + deps wiring.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from agents.app_generator.validators import validate_manifest
from catalog.bundle_catalog import BundleCatalog
from core.logging import get_logger
from orchestrators.preview_flow import PreviewFlow

logger = get_logger(__name__)

_DEFAULT_MOCK_HISTORY: list[dict[str, str]] = [
    {"role": "user", "content": "Generate a mock preview."}
]

# ---------------------------------------------------------------------------
# Output model
# ---------------------------------------------------------------------------


@dataclass
class MockPayload:
    """Assembled mock payload returned by MockPayloadBuilder."""

    bundle_key: str
    manifest: dict[str, Any]
    service_mocks: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


class MockPayloadBuilder:
    """Assembles MockPayload objects by running the production PreviewFlow.

    Usage::

        builder = MockPayloadBuilder(
            preview_flow=PreviewFlow(...),
            catalog=catalog,
            service_mocks=api_mocks_dict,
        )
        payload = builder.build("hr_hub")
        stores  = builder.build_stores("hr_hub")
        flags   = builder.build_flags("hr_hub")
    """

    def __init__(
        self,
        preview_flow: PreviewFlow,
        catalog: BundleCatalog,
        service_mocks: dict[str, Any] | None = None,
    ) -> None:
        self._preview_flow = preview_flow
        self._catalog = catalog
        self._service_mocks: dict[str, Any] = service_mocks or {}
        self._known_render_keys: frozenset[str] = frozenset(
            b.render_key for b in catalog.list_all() if b.render_key
        )
        self._known_bundle_keys: frozenset[str] = frozenset(
            b.bundle_key for b in catalog.list_all() if b.bundle_key
        )
        render_alias_map: dict[str, list[str]] = {}
        for bundle in catalog.list_all():
            render_alias_map.setdefault(bundle.render_key, []).append(bundle.bundle_key)
        self._render_alias_map = {k: sorted(v) for k, v in render_alias_map.items()}

    @property
    def known_render_keys(self) -> frozenset[str]:
        return self._known_render_keys

    @property
    def known_bundle_keys(self) -> frozenset[str]:
        return self._known_bundle_keys

    @property
    def render_alias_map(self) -> dict[str, list[str]]:
        return {k: list(v) for k, v in self._render_alias_map.items()}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build(
        self,
        bundle_key: str,
        manifest_override: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> MockPayload:
        """Assemble and return a complete MockPayload for the given render key.

        Runs preview flow to produce manifest.

        Args:
            bundle_key:           Render key (e.g. hr_hub, project_mgmt, ticketing).
            manifest_override: Caller-supplied manifest.
            session_id:           Used as the pipeline session identifier.
                                  A UUID is generated when omitted.
        """
        self._validate_bundle_key(bundle_key)
        resolved_session_id = session_id or str(uuid.uuid4())
        payload = self._preview_flow.run(
            session_id=resolved_session_id,
            bundle_key=bundle_key,
            conversation_history=_DEFAULT_MOCK_HISTORY,
        )

        if manifest_override is not None:
            validate_manifest(manifest_override)
            manifest: dict[str, Any] = dict(manifest_override)
            logger.info(
                "MockPayload built: bundle_key=%s source=override session=%s",
                bundle_key,
                resolved_session_id,
            )
        else:
            manifest = dict(payload.manifest)
            logger.info(
                "MockPayload built: bundle_key=%s source=pipeline session=%s",
                bundle_key,
                resolved_session_id,
            )

        logger.info(
            "MockPayload manifest served: bundle_key=%s schema=%s",
            bundle_key,
            manifest.get("schema_version"),
        )

        return MockPayload(
            bundle_key=bundle_key,
            manifest=manifest,
            service_mocks=self._service_mocks,
        )

    def build_stores(self, bundle_key: str) -> dict[str, Any]:
        """Return manifest for a bundle via the pipeline."""
        self._validate_bundle_key(bundle_key)
        payload = self._preview_flow.run(
            session_id=str(uuid.uuid4()),
            bundle_key=bundle_key,
            conversation_history=_DEFAULT_MOCK_HISTORY,
        )
        logger.info("MockPayload stores built: bundle_key=%s", bundle_key)
        return payload.manifest

    def build_flags(
        self, bundle_key: str
    ) -> tuple[list[dict[str, Any]], list[str], list[dict[str, Any]]]:
        """Return (feature_flags, permission_services, landing_pages) for bundle."""
        self._validate_bundle_key(bundle_key)
        payload = self._preview_flow.run(
            session_id=str(uuid.uuid4()),
            bundle_key=bundle_key,
            conversation_history=_DEFAULT_MOCK_HISTORY,
        )
        manifest = payload.manifest
        tenant = manifest.get("tenant", {}) if isinstance(manifest, dict) else {}
        logger.info("MockPayload flags built: bundle_key=%s", bundle_key)
        return [], [str(tenant.get("industry", ""))], []

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _validate_bundle_key(self, bundle_key: str) -> None:
        if bundle_key not in self._known_bundle_keys:
            raise ValueError(f"Unknown bundle key: {bundle_key!r}")


# ---------------------------------------------------------------------------
# Module-level KNOWN_RENDER_KEYS shim
# ---------------------------------------------------------------------------
# The router imports this name directly. It is populated by
# MockPayloadBuilder.__init__ at runtime; this sentinel keeps the import from
# failing before any builder is constructed.
KNOWN_RENDER_KEYS: frozenset[str] = frozenset()
