"""Orchestrator: runs the preview pipeline and assembles the AppPayload."""

from __future__ import annotations

from typing import Any, Optional

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
        dashboard_client: Optional[DashboardClient] = None,
        dashboard_template_registry: Optional[DashboardTemplateRegistry] = None,
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
        """Execute the preview pipeline, enrich with dashboard widgets, return AppPayload.

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
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "session=%s — dashboard enrichment error: %s", session_id, exc
            )
            return

        if response is None:
            return

        widgets: list = (
            response.get("debug_payload", {}).get("widgets", [])
        )
        dashboard_info: dict = response.get("dashboard", {})

        stores: dict = dummy_data_json.setdefault("stores", {})
        stores["dashboard_widgets"] = widgets
        if dashboard_info:
            stores["dashboard_meta"] = {
                "id": dashboard_info.get("id"),
                "name": dashboard_info.get("name"),
                "url": dashboard_info.get("url"),
            }

        logger.info(
            "session=%s — dashboard enrichment complete: %d widgets injected",
            session_id,
            len(widgets),
        )
