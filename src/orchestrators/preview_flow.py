"""Orchestrator: runs the preview pipeline and assembles the AppPayload."""

from __future__ import annotations

from typing import Any

from agents.preview_generator.dashboard.client import DashboardClient
from agents.preview_generator.dashboard.personalizer import personalize_template
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
    ) -> None:
        self._preview_gen = preview_generator_service
        self._display_names = bundle_display_names
        self._dashboard_client = dashboard_client
        self._dashboard_templates = dashboard_template_registry

    def run(
        self,
        session_id: str,
        bundle_key: str,
        conversation_history: list[dict],
        extraction_result: ExtractionResult | None = None,
        preselected_intent: str | None = None,
    ) -> AppPayload:
        """Execute the preview pipeline, enrich with dashboard widgets.

        Returns AppPayload.

        Args:
            extraction_result:  Dev A's accumulated ExtractionResult. When present,
                                the pipeline skips its own keyword scan / LLM call.
            preselected_intent: User-chosen intent before conversation started.
        """
        session_logger = get_session_logger(__name__, session_id)
        session_logger.info("Running preview flow for bundle=%s", bundle_key)

        generation_json, dummy_data_json, user_context = self._preview_gen.generate(
            session_id=session_id,
            bundle_key=bundle_key,
            conversation_history=conversation_history,
            extraction_result=extraction_result,
            preselected_intent=preselected_intent,
        )

        # --- Dashboard enrichment (best-effort, never blocks preview) ---
        self._enrich_dashboard_widgets(
            session_id=session_id,
            bundle_key=bundle_key,
            dummy_data_json=dummy_data_json,
            user_context=user_context,
            conversation_history=conversation_history,
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

    def _enrich_dashboard_widgets(
        self,
        session_id: str,
        bundle_key: str,
        dummy_data_json: dict,
        user_context: Any,
        conversation_history: list[dict] | None = None,
    ) -> None:
        """Attempt to populate dashboard_widgets in stores via the external service.

        Mutates ``dummy_data_json`` in place. All failures are swallowed so the
        caller always gets a valid (if widget-less) payload.
        """
        if self._dashboard_client is None or self._dashboard_templates is None:
            return

        template = self._dashboard_templates.get(bundle_key)
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

        stores: dict = dummy_data_json.setdefault("stores", {})
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
