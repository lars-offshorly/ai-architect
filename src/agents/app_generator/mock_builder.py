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

from agents.app_generator.validators import validate_dummy_data_json
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
        self._validate_bundle_key(bundle_key)
        resolved_session_id = session_id or str(uuid.uuid4())
        payload = self._preview_flow.run(
            session_id=resolved_session_id,
            bundle_key=bundle_key,
            conversation_history=_DEFAULT_MOCK_HISTORY,
        )

        if dummy_data_override is not None:
            validate_dummy_data_json(dummy_data_override, bundle_key)
            dummy_data_json: dict[str, Any] = _normalize_dummy_data_json(
                dict(dummy_data_override)
            )
            if not dummy_data_json.get("session_id"):
                dummy_data_json = {**dummy_data_json, "session_id": resolved_session_id}
            logger.info(
                "MockPayload built: bundle_key=%s source=override session=%s",
                bundle_key,
                resolved_session_id,
            )
        else:
            dummy_data_json = payload.dummy_data_json
            logger.info(
                "MockPayload built: bundle_key=%s source=pipeline session=%s",
                bundle_key,
                resolved_session_id,
            )

        generation_json: dict[str, Any] = payload.generation_json
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
        self._validate_bundle_key(bundle_key)
        payload = self._preview_flow.run(
            session_id=str(uuid.uuid4()),
            bundle_key=bundle_key,
            conversation_history=_DEFAULT_MOCK_HISTORY,
        )
        logger.info("MockPayload stores built: bundle_key=%s", bundle_key)
        return payload.dummy_data_json

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
        generation_json = payload.generation_json
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

    def _validate_bundle_key(self, bundle_key: str) -> None:
        if bundle_key not in self._known_bundle_keys:
            raise ValueError(f"Unknown bundle key: {bundle_key!r}")


def _normalize_dummy_data_json(dummy_data_json: dict[str, Any]) -> dict[str, Any]:
    """Normalize dummy_data_json overrides to keep downstream contracts stable."""
    stores = dummy_data_json.get("stores")
    if not isinstance(stores, dict):
        return dummy_data_json

    normalized_stores = dict(stores)
    if "dashboard_generation_output" not in normalized_stores:
        widgets_raw = normalized_stores.get("dashboard_widgets")
        widget_count = len(widgets_raw) if isinstance(widgets_raw, list) else 0
        normalized_stores["dashboard_generation_output"] = {
            "success": True,
            "dashboard": {"id": "dash-preview", "name": "Preview Dashboard", "url": None},
            "widgets": {"total": widget_count},
            "execution_time": "0m 1s",
            "errors": [],
            "debug_payload": {"total_widgets": widget_count},
            "generation_metadata": {"widgets_extracted": widget_count},
        }

    # KPI IDs are expected downstream; best-effort backfill when missing.
    kpis = normalized_stores.get("kpis")
    if isinstance(kpis, list):
        patched_kpis: list[object] = []
        for idx, item in enumerate(kpis, start=1):
            if not isinstance(item, dict):
                patched_kpis.append(item)
                continue
            patched = dict(item)
            if not patched.get("id"):
                key = patched.get("key")
                patched["id"] = key if isinstance(key, str) and key else idx
            patched_kpis.append(patched)
        normalized_stores["kpis"] = patched_kpis

    return {**dummy_data_json, "stores": normalized_stores}


# ---------------------------------------------------------------------------
# Module-level KNOWN_RENDER_KEYS shim
# ---------------------------------------------------------------------------
# The router imports this name directly. It is populated by
# MockPayloadBuilder.__init__ at runtime; this sentinel keeps the import from
# failing before any builder is constructed.
KNOWN_RENDER_KEYS: frozenset[str] = frozenset()
