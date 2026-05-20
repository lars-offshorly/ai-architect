"""Orchestrator: runs the preview pipeline and assembles the AppPayload."""

from __future__ import annotations

from typing import Any

from agents.preview_generator.bundle_template_loader import (
    PIPELINE_OWNED_STORE_KEYS,
    BundleTemplateLoader,
)
from agents.preview_generator.dashboard.static_ids import DASHBOARD_IDS
from agents.preview_generator.dashboard.templates import DashboardTemplateRegistry
from agents.tenant_provisioning.service import TenantProvisioningService
from core.logging import get_logger, get_session_logger
from domain.models.app_payload import AppPayload
from domain.models.extraction_result import ExtractionResult
from domain.services.registry_facade import RegistryFacade

logger = get_logger(__name__)

_CANONICAL_AUTHORITATIVE_STORE_KEYS: frozenset[str] = frozenset(
    {
        "queues",
        "projects",
        "kpis",
        "employees",
        "request_types",
        "canonical_dashboards",
    }
)


class PreviewFlow:
    """Orchestrates preview generation and assembles the final AppPayload.

    AppGeneratorService is intentionally bypassed here.
    AppGeneratorService.assemble() loads generation_json from a static disk
    template and ignores any preview_data passed to it, so it cannot carry
    our pipeline output. AppPayload is built directly from the pipeline result.

    Dashboard enrichment is performed after the core pipeline completes by
    resolving and injecting pre-generated static widget layouts.

    If any step of the enrichment fails the preview is returned without
    dashboard widgets — the failure is logged but never re-raised.
    """

    def __init__(
        self,
        preview_generator_service: Any,
        bundle_display_names: dict[str, str],
        registry_facade: RegistryFacade | None = None,
        bundle_template_loader: BundleTemplateLoader | None = None,
        static_dashboard_outputs: DashboardTemplateRegistry | None = None,
        tenant_provisioning_service: TenantProvisioningService | None = None,
    ) -> None:
        self._preview_gen = preview_generator_service
        self._display_names = bundle_display_names
        self._registry_facade = registry_facade
        self._bundle_template_loader = bundle_template_loader
        self._static_dashboard_outputs = static_dashboard_outputs
        self._tenant_provisioning_service = tenant_provisioning_service

    def run(
        self,
        session_id: str,
        bundle_key: str,
        conversation_history: list[dict],
        extraction_result: ExtractionResult | None = None,
        preselected_intent: str | None = None,
        variant_key: str | None = None,
    ) -> AppPayload:
        """Execute the preview pipeline, enrich with dashboard widgets.

        Returns AppPayload.

        Args:
            extraction_result:  Dev A's accumulated ExtractionResult. When present,
                                the pipeline skips its own keyword scan / LLM call.
            preselected_intent: User-chosen intent before conversation started.
            variant_key:        Legacy compatibility input; ignored by canonical
                                runtime path.
        """
        _ = variant_key
        session_logger = get_session_logger(__name__, session_id)
        session_logger.info(
            "Running preview flow for bundle=%s",
            bundle_key,
        )

        generation_json, dummy_data_json, user_context = self._preview_gen.generate(
            session_id=session_id,
            bundle_key=bundle_key,
            conversation_history=conversation_history,
            extraction_result=extraction_result,
            preselected_intent=preselected_intent,
        )
        preview_warnings: list[dict[str, str]] = []

        # --- Canonical manifest payload overlay (best-effort) ---
        if self._registry_facade is not None:
            self._registry_facade.build_payload_stores(bundle_key, dummy_data_json)

        # --- Static bundle template overlay (best-effort) ---
        # Replaces dynamically generated operational stores (tickets, projects,
        # tasks …) with realistic, domain-specific fixtures from app-0*.json.
        # KPIs and dashboard_widgets are intentionally left to the pipeline and
        # the dashboard enrichment step respectively.
        template_warning = self._apply_bundle_template(
            session_id=session_id,
            bundle_key=bundle_key,
            dummy_data_json=dummy_data_json,
            user_context=user_context,
        )
        if template_warning is not None:
            preview_warnings.append(template_warning)

        # --- Dashboard enrichment (best-effort, never blocks preview) ---
        self._enrich_dashboard_widgets(
            session_id=session_id,
            bundle_key=bundle_key,
            dummy_data_json=dummy_data_json,
            user_context=user_context,
        )

        if preview_warnings:
            generation_json["preview_warnings"] = preview_warnings

        v2_manifest = self._build_v2_manifest(
            session_id=session_id,
            bundle_key=bundle_key,
            conversation_history=conversation_history,
        )

        payload = AppPayload(
            session_id=session_id,
            bundle_key=bundle_key,
            display_name=self._display_names.get(bundle_key, bundle_key),
            modules=generation_json.get("modules", []),
            generation_json=generation_json,
            dummy_data_json=dummy_data_json,
            v2_manifest=v2_manifest,
        )

        session_logger.info(
            "Preview flow complete for session=%s modules=%s dashboard_widgets=%d",
            session_id,
            payload.modules,
            len(dummy_data_json.get("stores", {}).get("dashboard_widgets", [])),
        )
        return payload

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _apply_bundle_template(
        self,
        session_id: str,
        bundle_key: str,
        dummy_data_json: dict,
        user_context: Any,
        variant_key: str | None = None,
    ) -> dict[str, str] | None:
        """Overlay operational stores from a static app-0*.json variant.

        Overlays the template ``stores`` dict into ``dummy_data_json["stores"]``.
        Pipeline-owned
        keys (``kpis``) and dashboard-owned keys (``dashboard_widgets``,
        ``dashboard_generation_output``) are skipped.

        All failures are swallowed; the preview is returned with pipeline-
        generated data if anything goes wrong.
        """
        if self._bundle_template_loader is None:
            return {
                "code": "bundle_template_loader_unavailable",
                "message": "Static bundle template loader is not initialized.",
            }

        _ = user_context
        _ = variant_key
        try:
            template = self._bundle_template_loader.load(bundle_key)
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning(
                "session=%s — bundle template load error: %s", session_id, exc
            )
            return {
                "code": "bundle_template_overlay_failed",
                "message": str(exc),
            }

        if template is None:
            logger.info(
                "session=%s — no bundle template for bundle=%s, skipping overlay",
                session_id,
                bundle_key,
            )
            return {
                "code": "bundle_template_missing",
                "message": "No static bundle template found for bundle/variant.",
            }

        template_stores: dict = template.get("stores", {})
        if not template_stores:
            return None

        stores: dict = dummy_data_json.setdefault("stores", {})
        overlaid_keys: list[str] = []
        for key, value in template_stores.items():
            if key in PIPELINE_OWNED_STORE_KEYS:
                continue
            if key in _CANONICAL_AUTHORITATIVE_STORE_KEYS:
                continue
            stores[key] = value
            overlaid_keys.append(key)

        source_file = template.get("_source_file", "unknown")
        logger.info(
            "session=%s — bundle template overlay: file=%s stores_overlaid=%s",
            session_id,
            source_file,
            overlaid_keys,
        )
        return None

    def _enrich_dashboard_widgets(
        self,
        session_id: str,
        bundle_key: str,
        dummy_data_json: dict,
        user_context: Any,
        variant_key: str | None = None,
    ) -> None:
        """Populate ``stores.dashboard_widgets`` from static pre-generated output."""
        _ = user_context
        _ = variant_key
        stores: dict = dummy_data_json.setdefault("stores", {})

        payload = self._resolve_static_payload(session_id, bundle_key)
        if payload is None:
            stores["dashboard_widgets"] = []
            return

        dashboard_obj = payload["widgets"][0]
        raw_widgets = dashboard_obj["widget_templates"]
        widgets = self._coerce_dashboard_widgets(raw_widgets)
        stores["dashboard_widgets"] = widgets
        self._patch_generation_output(stores, dashboard_obj, widgets)

        logger.info(
            "session=%s: static dashboard output injected bundle=%s widgets=%d",
            session_id,
            bundle_key,
            len(widgets),
        )

    def _resolve_static_payload(
        self,
        session_id: str,
        bundle_key: str,
    ) -> dict | None:
        """Return the full template payload, or None on any failure."""
        if self._static_dashboard_outputs is None:
            logger.warning(
                "session=%s: DashboardTemplateRegistry not initialized", session_id
            )
            return None

        payload = self._static_dashboard_outputs.get(bundle_key)
        if payload is None:
            logger.warning(
                "session=%s: no static dashboard output for bundle=%s",
                session_id,
                bundle_key,
            )
            return None

        dashboard_entries = payload.get("widgets") or []
        if not dashboard_entries or not dashboard_entries[0].get("widget_templates"):
            logger.warning(
                "session=%s: empty widget_templates in static dashboard output "
                "for bundle=%s",
                session_id,
                bundle_key,
            )
            return None

        return payload

    @staticmethod
    def _patch_generation_output(
        stores: dict,
        dashboard_obj: dict,
        widgets: list,
    ) -> None:
        """Sync ``dashboard_generation_output`` with the injected static payload."""
        gen_output = stores.get("dashboard_generation_output")
        if not isinstance(gen_output, dict):
            return

        dash_name = dashboard_obj.get("name") or "Tickets Dashboard"
        dash_id = dashboard_obj.get("dashboard_external_id") or DASHBOARD_IDS.get(
            dash_name, DASHBOARD_IDS["Tickets Dashboard"]
        )

        dashboard = gen_output.setdefault("dashboard", {})
        dashboard["name"] = dash_name
        dashboard["external_id"] = dash_id

        type_counts: dict[str, int] = {
            "text": 0,
            "number": 0,
            "bar": 0,
            "hbar": 0,
            "pie": 0,
            "line": 0,
            "scatter": 0,
            "list": 0,
            "combo": 0,
            "embed": 0,
        }
        for widget in widgets:
            wtype = widget.get("type")
            if isinstance(wtype, str) and wtype in type_counts:
                type_counts[wtype] += 1
        gen_output["widgets"] = {**type_counts, "total": len(widgets)}

        meta = gen_output.setdefault("generation_metadata", {})
        meta["widgets_extracted"] = len(widgets)
        meta["widgets_explicit"] = len(widgets)

    def _build_v2_manifest(
        self,
        session_id: str,
        bundle_key: str,
        conversation_history: list[dict],
    ) -> dict[str, object] | None:
        """Return v2 manifest from TenantProvisioningService when available."""
        if self._tenant_provisioning_service is None:
            return None
        user_message = _last_user_message(conversation_history)
        try:
            return self._tenant_provisioning_service.provision(
                bundle_key=bundle_key,
                user_message=user_message,
                session_id=session_id,
            )
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning(
                "session=%s — v2 manifest provisioning failed for bundle=%s: %s",
                session_id,
                bundle_key,
                exc,
            )
            return None

    @staticmethod
    def _coerce_dashboard_widgets(raw_widgets: Any) -> list[dict[str, Any]]:
        """Coerce static dashboard widget lists into app-generator-safe schema.

        App finalization validates dummy_data_json via DummyDataJsonSchema, which
        expects dashboard widgets to include: id, type, title, position.

        Static dashboard output files may be in either shape:
        - canonical widgets: {id, type, title, position:{row,col,width,height}, ...}
        - external-only widgets: {widget_template_external_id, name}
        """
        if not isinstance(raw_widgets, list):
            return []

        # Already canonical.
        if raw_widgets and isinstance(raw_widgets[0], dict):
            first = raw_widgets[0]
            if all(k in first for k in ("id", "type", "title", "position")):
                return [w for w in raw_widgets if isinstance(w, dict)]

        canonical: list[dict[str, Any]] = []
        for idx, w in enumerate(raw_widgets):
            if not isinstance(w, dict):
                continue

            title = w.get("title") or w.get("name") or f"Widget {idx + 1}"
            external_id = w.get("widget_template_external_id")
            wid = w.get("id")
            if not isinstance(wid, str) or not wid:
                wid = (
                    f"widget-{external_id}"
                    if external_id is not None
                    else f"widget-{idx + 1}"
                )

            # Default to a numeric widget type; frontend can still render generically.
            wtype = w.get("type")
            if not isinstance(wtype, str) or not wtype:
                wtype = "number"

            position = w.get("position")
            if not isinstance(position, dict) or not all(
                k in position for k in ("row", "col", "width", "height")
            ):
                position = {
                    "row": idx // 2,
                    "col": idx % 2,
                    "width": 1,
                    "height": 1,
                }

            canonical.append(
                {
                    "id": wid,
                    "type": wtype,
                    "title": str(title),
                    "position": position,
                }
            )

        return canonical


def _last_user_message(conversation_history: list[dict]) -> str:
    """Return the content of the last user-role message, or empty string."""
    for msg in reversed(conversation_history):
        if msg.get("role") == "user":
            return str(msg.get("content", ""))
    return ""
