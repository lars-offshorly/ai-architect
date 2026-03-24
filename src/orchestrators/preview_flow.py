from __future__ import annotations

from core.logging import get_logger, get_session_logger
from domain.models.app_payload import AppPayload

logger = get_logger(__name__)


class PreviewFlow:
    """Orchestrates preview generation and assembles the final AppPayload.

    AppGeneratorService is intentionally bypassed here.
    AppGeneratorService.assemble() loads generation_json from a static disk
    template and ignores any preview_data passed to it, so it cannot carry
    our pipeline output. AppPayload is built directly from the pipeline result.
    """

    def __init__(
        self,
        preview_generator_service: object,
        bundle_display_names: dict[str, str],
    ) -> None:
        self._preview_gen = preview_generator_service  # type: ignore[assignment]
        self._display_names = bundle_display_names

    def run(
        self,
        session_id: str,
        bundle_key: str,
        conversation_history: list[dict],
    ) -> AppPayload:
        session_logger = get_session_logger(__name__, session_id)
        session_logger.info("Running preview flow for bundle=%s", bundle_key)

        generation_json, dummy_data_json = self._preview_gen.generate(
            session_id=session_id,
            bundle_key=bundle_key,
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
            "Preview flow complete for session=%s modules=%s",
            session_id,
            modules,
        )
        return payload
