"""Orchestrator: runs the preview pipeline and assembles the AppPayload."""

from __future__ import annotations

from typing import Any

from agents.preview_generator.bundle_template_loader import (
    PIPELINE_OWNED_STORE_KEYS,
    BundleTemplateLoader,
)
from agents.preview_generator.dashboard.static_ids import DASHBOARD_IDS
from agents.preview_generator.dashboard.templates import DashboardTemplateRegistry
from core.logging import get_logger, get_session_logger
from domain.models.app_payload import AppPayload
from domain.models.extraction_result import ExtractionResult

logger = get_logger(__name__)


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
        bundle_template_loader: BundleTemplateLoader | None = None,
        static_dashboard_outputs: DashboardTemplateRegistry | None = None,
    ) -> None:
        self._preview_gen = preview_generator_service
        self._display_names = bundle_display_names
        self._bundle_template_loader = bundle_template_loader
        self._static_dashboard_outputs = static_dashboard_outputs

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
            variant_key:        Bundle variant (``app-01``/``app-02``/``app-03``)
                                chosen by the interpreter's VariantSelector. When
                                omitted, ``extraction_result.bundle_variant_key``
                                is used; when both are absent, the default variant
                                is used for template + dashboard resolution.
        """
        session_logger = get_session_logger(__name__, session_id)
        session_logger.info(
            "Running preview flow for bundle=%s variant=%s",
            bundle_key,
            variant_key
            or (
                extraction_result.bundle_variant_key
                if extraction_result is not None
                else None
            ),
        )

        generation_json, dummy_data_json, output_v2, user_context = self._preview_gen.generate(
            session_id=session_id,
            bundle_key=bundle_key,
            conversation_history=conversation_history,
            extraction_result=extraction_result,
            preselected_intent=preselected_intent,
        )
        preview_warnings: list[dict[str, str]] = []

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
            variant_key=variant_key
            or (
                extraction_result.bundle_variant_key
                if extraction_result is not None
                else None
            ),
        )
        if template_warning is not None:
            preview_warnings.append(template_warning)

        # --- Dashboard enrichment (best-effort, never blocks preview) ---
        knit_builder_payload = self._enrich_dashboard_widgets(
            session_id=session_id,
            bundle_key=bundle_key,
            dummy_data_json=dummy_data_json,
            user_context=user_context,
            variant_key=variant_key
            or (
                extraction_result.bundle_variant_key
                if extraction_result is not None
                else None
            ),
        )
        generation_schema_val: dict = knit_builder_payload or {
            "dashboards": None,
            "projects": None,
            "tickets": None,
            "hrHub": None,
            "kpi": None,
        }
        generation_json["knit_builder_payload"] = generation_schema_val

        if preview_warnings:
            generation_json["preview_warnings"] = preview_warnings

        sample_data_val: dict = (
            output_v2.sample_data.model_dump() if output_v2 is not None else {}
        )

        payload = AppPayload(
            session_id=session_id,
            bundle_key=bundle_key,
            display_name=self._display_names.get(bundle_key, bundle_key),
            modules=generation_json.get("modules", []),
            generation_json=generation_json,
            dummy_data_json=dummy_data_json,
            generation_schema=generation_schema_val,
            sample_data=sample_data_val,
        )

        session_logger.info(
            "Preview flow complete for session=%s modules=%s dashboard_widgets=%d "
            "generation_schema_keys=%s sample_data_services=%s",
            session_id,
            payload.modules,
            len(dummy_data_json.get("stores", {}).get("dashboard_widgets", [])),
            list(payload.generation_schema.keys()),
            list(payload.sample_data.get("services", {}).keys()) if payload.sample_data else [],
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

        Resolves the variant by ``variant_key`` (emitted upstream by the
        interpreter's ``VariantSelector``) and overlays the variant's
        ``stores`` dict into ``dummy_data_json["stores"]``. Pipeline-owned
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

        resolved_variant_key = variant_key or _extract_variant_key(user_context)
        try:
            template = self._bundle_template_loader.load(
                bundle_key, resolved_variant_key
            )
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
    ) -> dict | None:
        """Populate ``stores.dashboard_widgets`` from static pre-generated output.

        Returns a ``GenerationSchema``-compatible ``knit_builder_payload`` dict
        when enrichment succeeds, or ``None`` when no static payload is available.
        """
        resolved_variant_key = variant_key or _extract_variant_key(user_context)
        stores: dict = dummy_data_json.setdefault("stores", {})

        payload = self._resolve_static_payload(
            session_id, bundle_key, resolved_variant_key
        )
        if payload is None:
            stores["dashboard_widgets"] = []
            return None

        dashboard_obj = payload["widgets"][0]
        raw_widgets = dashboard_obj["widget_templates"]
        widgets = self._coerce_dashboard_widgets(raw_widgets)
        stores["dashboard_widgets"] = widgets
        self._patch_generation_output(stores, dashboard_obj, widgets)

        logger.info(
            "session=%s: static dashboard output injected "
            "bundle=%s variant=%s widgets=%d",
            session_id,
            bundle_key,
            resolved_variant_key,
            len(widgets),
        )
        return self._build_knit_builder_payload(dashboard_obj, raw_widgets)

    def _resolve_static_payload(
        self,
        session_id: str,
        bundle_key: str,
        resolved_variant_key: str | None,
    ) -> dict | None:
        """Return the full template payload, or None on any failure."""
        if self._static_dashboard_outputs is None:
            logger.warning(
                "session=%s: DashboardTemplateRegistry not initialized", session_id
            )
            return None

        payload = self._static_dashboard_outputs.get(bundle_key, resolved_variant_key)
        if payload is None:
            logger.warning(
                "session=%s: no static dashboard output for bundle=%s variant=%s",
                session_id,
                bundle_key,
                resolved_variant_key,
            )
            return None

        dashboard_entries = payload.get("widgets") or []
        if not dashboard_entries or not dashboard_entries[0].get("widget_templates"):
            logger.warning(
                "session=%s: empty widget_templates in static dashboard output "
                "for bundle=%s variant=%s",
                session_id,
                bundle_key,
                resolved_variant_key,
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

    @staticmethod
    def _build_knit_builder_payload(
        dashboard_obj: dict,
        raw_widgets: list,
    ) -> dict:
        """Build a ``GenerationSchema``-compatible payload for the knit-builder API.

        Maps the enriched dashboard template and its widget templates into the
        structure expected by ``POST /organizations/me/generate/``.
        Modules other than ``dashboards`` are ``null`` until the backend defines
        their schemas.
        """
        dashboard_id = dashboard_obj.get("dashboard_external_id")
        widget_templates = [
            {"id": w["widget_template_external_id"], "name": None}
            for w in raw_widgets
            if isinstance(w, dict)
            and isinstance(w.get("widget_template_external_id"), int)
        ]
        dashboard_templates = (
            [{"id": dashboard_id, "name": None, "widgetTemplates": widget_templates}]
            if isinstance(dashboard_id, int)
            else []
        )
        return {
            "dashboards": (
                {"dashboardTemplates": dashboard_templates}
                if dashboard_templates
                else None
            ),
            "projects": None,
            "tickets": None,
            "hrHub": None,
            "kpi": None,
        }

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


def _extract_variant_key(user_context: Any) -> str | None:
    """Pull ``bundle_variant_key`` off a ``UserContext`` / ExtractedInfo-like object.

    Uses attribute access first (pydantic models, dataclasses), then falls
    back to ``.slots['bundle_variant_key']`` when present.
    """
    if user_context is None:
        return None
    value = getattr(user_context, "bundle_variant_key", None)
    if isinstance(value, str) and value:
        return value
    slots = getattr(user_context, "slots", None)
    if isinstance(slots, dict):
        slot_value = slots.get("bundle_variant_key")
        if isinstance(slot_value, str) and slot_value:
            return slot_value
    return None
