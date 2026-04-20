"""Orchestrator: runs the preview pipeline and assembles the AppPayload."""

from __future__ import annotations

from typing import Any

from agents.preview_generator.bundle_template_loader import (
    _PIPELINE_OWNED_STORE_KEYS,
    BundleTemplateLoader,
)
from agents.preview_generator.dashboard.client import DashboardClient
from agents.preview_generator.dashboard.personalizer import personalize_template
from agents.preview_generator.dashboard.static_output_registry import (
    StaticDashboardOutputRegistry,
)
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

    Dashboard enrichment is performed after the core pipeline completes:
    1. Look up a template for the bundle key.
    2. Personalize it from the pipeline's extracted UserContext.
    3. POST to the dashboard generation service.
    4. Inject the returned widgets into dummy_data_json.stores.dashboard_widgets.

    If any step of the enrichment fails the preview is returned without
    dashboard widgets — the failure is logged but never re-raised.
    """

    def __init__(
        self,
        preview_generator_service: Any,
        bundle_display_names: dict[str, str],
        dashboard_client: DashboardClient | None = None,
        dashboard_template_registry: DashboardTemplateRegistry | None = None,
        bundle_template_loader: BundleTemplateLoader | None = None,
        static_dashboard_outputs: StaticDashboardOutputRegistry | None = None,
    ) -> None:
        self._preview_gen = preview_generator_service
        self._display_names = bundle_display_names
        self._dashboard_client = dashboard_client
        self._dashboard_templates = dashboard_template_registry
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
        resolved_variant_key = variant_key or (
            extraction_result.bundle_variant_key
            if extraction_result is not None
            else None
        )
        session_logger.info(
            "Running preview flow for bundle=%s variant=%s",
            bundle_key,
            resolved_variant_key,
        )

        generation_json, dummy_data_json, user_context = self._preview_gen.generate(
            session_id=session_id,
            bundle_key=bundle_key,
            conversation_history=conversation_history,
            extraction_result=extraction_result,
            preselected_intent=preselected_intent,
        )

        # --- Static bundle template overlay (best-effort) ---
        # Replaces dynamically generated operational stores (tickets, projects,
        # tasks …) with realistic, domain-specific fixtures from app-0*.json.
        # KPIs and dashboard_widgets are intentionally left to the pipeline and
        # the dashboard enrichment step respectively.
        self._apply_bundle_template(
            session_id=session_id,
            bundle_key=bundle_key,
            dummy_data_json=dummy_data_json,
            user_context=user_context,
            variant_key=resolved_variant_key,
        )

        # --- Dashboard enrichment (best-effort, never blocks preview) ---
        self._enrich_dashboard_widgets(
            session_id=session_id,
            bundle_key=bundle_key,
            dummy_data_json=dummy_data_json,
            user_context=user_context,
            conversation_history=conversation_history,
            variant_key=resolved_variant_key,
        )

        display_name = self._display_names.get(bundle_key, bundle_key)
        modules: list[str] = generation_json.get("modules", [])

        payload = AppPayload(
            session_id=session_id,
            bundle_key=bundle_key,
            display_name=display_name,
            modules=modules,
            generation_json=generation_json,
            dummy_data_json=dummy_data_json,
        )

        session_logger.info(
            "Preview flow complete for session=%s modules=%s dashboard_widgets=%d",
            session_id,
            modules,
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
    ) -> None:
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
            return

        resolved_variant_key = variant_key or _extract_variant_key(user_context)
        try:
            template = self._bundle_template_loader.load(
                bundle_key, resolved_variant_key
            )
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning(
                "session=%s — bundle template load error: %s", session_id, exc
            )
            return

        if template is None:
            logger.info(
                "session=%s — no bundle template for bundle=%s, skipping overlay",
                session_id,
                bundle_key,
            )
            return

        template_stores: dict = template.get("stores", {})
        if not template_stores:
            return

        stores: dict = dummy_data_json.setdefault("stores", {})
        overlaid_keys: list[str] = []
        for key, value in template_stores.items():
            if key in _PIPELINE_OWNED_STORE_KEYS:
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

    def _enrich_dashboard_widgets(
        self,
        session_id: str,
        bundle_key: str,
        dummy_data_json: dict,
        user_context: Any,
        conversation_history: list[dict] | None = None,
        variant_key: str | None = None,
    ) -> None:
        """Populate dashboard_widgets in stores, preferring pre-generated static outputs.

        Resolution order:
        1. ``StaticDashboardOutputRegistry`` — pre-generated widget layout (no service call).
        2. Live ``DashboardClient`` — personalises + POSTs to the dashboard gen service.

        Mutates ``dummy_data_json`` in place. All failures are swallowed so the
        caller always gets a valid (if widget-less) payload.
        """
        resolved_variant_key = variant_key or _extract_variant_key(user_context)

        # --- Static pre-generated output (preferred, no network call) ---
        if self._static_dashboard_outputs is not None:
            widgets = self._static_dashboard_outputs.get_widgets(
                bundle_key, resolved_variant_key
            )
            if widgets is not None:
                stores: dict = dummy_data_json.setdefault("stores", {})
                stores["dashboard_widgets"] = widgets
                logger.info(
                    "session=%s — static dashboard output: %d widgets injected for bundle=%s",
                    session_id,
                    len(widgets),
                    bundle_key,
                )
                return

        # --- Live dashboard gen service (fallback for bundles without static output) ---
        if self._dashboard_client is None or self._dashboard_templates is None:
            return

        template = self._dashboard_templates.get(bundle_key, resolved_variant_key)
        if template is None:
            logger.info(
                "session=%s — no dashboard template for bundle=%s, skipping enrichment",
                session_id,
                bundle_key,
            )
            return

        try:
            personalized = personalize_template(
                template,
                user_context,
                bundle_key,
                conversation_history=conversation_history or [],
            )
            response = self._dashboard_client.generate(personalized)
        except (AttributeError, KeyError, RuntimeError, TypeError, ValueError) as exc:
            logger.warning(
                "session=%s — dashboard enrichment error: %s", session_id, exc
            )
            return

        if response is None:
            return

        raw_widgets = response.get("debug_payload", {}).get("widgets", [])
        widgets = self._to_internal_widgets(raw_widgets)

        stores = dummy_data_json.setdefault("stores", {})
        stores["dashboard_generation_output"] = response
        stores["dashboard_widgets"] = widgets

        logger.info(
            "session=%s — dashboard enrichment complete: %d widgets injected",
            session_id,
            len(widgets),
        )

    @staticmethod
    def _to_internal_widgets(  # pylint: disable=too-many-branches
        raw_widgets: Any,
    ) -> list[dict[str, object]]:
        """Map external dashboard debug widgets to internal widget layout shape.

        Handles CJ's dashboard generation output format:
        - Maps typeId (int) to type (string)
        - Extracts positioning from settings.xAxis/yAxis/width/height
        - Handles chartType for chart widgets
        """
        if not isinstance(raw_widgets, list):
            return []

        # CJ's typeId → internal type string mapping
        type_id_map = {
            1: "number",
            2: "text",
            3: "bar",  # Chart widget - refined by chartType
            4: "list",
        }

        widgets: list[dict[str, object]] = []
        for idx, raw in enumerate(raw_widgets, start=1):
            if not isinstance(raw, dict):
                continue

            # Extract type from typeId
            type_id = raw.get("typeId")
            widget_type = (
                type_id_map.get(type_id) if isinstance(type_id, int) else None
            ) or "number"

            # For chart widgets (typeId=3), refine type from settings.chartType
            if type_id == 3:
                settings = raw.get("settings", {})
                if isinstance(settings, dict):
                    chart_type = settings.get("chartType", "bar")
                    if chart_type == "barHorizontal":
                        widget_type = "hbar"
                    elif chart_type in ("pie", "line", "scatter"):
                        widget_type = chart_type
                    # else: keep "bar" as default

            # Extract title from name or title field
            title = raw.get("name") or raw.get("title")
            if not isinstance(title, str) or not title.strip():
                title = f"Widget {idx}"

            # Extract positioning from settings
            settings = raw.get("settings", {})
            if isinstance(settings, dict) and "yAxis" in settings:
                # Use CJ's positioning from settings
                row = settings.get("yAxis", 0)
                col = settings.get("xAxis", 0)
                width = settings.get("width", 2)
                height = settings.get("height", 1)
            else:
                # Fallback to 2-column grid layout
                row = (idx - 1) // 2
                col = ((idx - 1) % 2) * 2
                width = 2
                height = 1

            # Extract widget ID from settings or raw.id
            widget_id = None
            if isinstance(settings, dict):
                widget_id = settings.get("id")
            if widget_id is None:
                widget_id = raw.get("id")
            if widget_id is None:
                widget_id = idx

            widgets.append(
                {
                    "id": f"widget-{widget_id}",
                    "type": widget_type,
                    "title": title,
                    "position": {
                        "row": row,
                        "col": col,
                        "width": width,
                        "height": height,
                    },
                }
            )

        return widgets


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
