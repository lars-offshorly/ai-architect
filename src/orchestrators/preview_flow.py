from __future__ import annotations

from core.logging import get_logger, get_session_logger
from domain.models.app_payload import AppPayload
from domain.models.extracted_info import ExtractedInfo

logger = get_logger(__name__)


class PreviewFlow:
    def __init__(
        self,
        preview_generator_service: object,
        app_generator_service: object,
        bundle_display_names: dict[str, str],
    ) -> None:
        self._preview_gen = preview_generator_service  # type: ignore[assignment]
        self._app_gen = app_generator_service  # type: ignore[assignment]
        self._display_names = bundle_display_names

    def run(
        self,
        session_id: str,
        bundle_key: str,
        extracted: ExtractedInfo,
    ) -> AppPayload:
        session_logger = get_session_logger(__name__, session_id)
        session_logger.info("Running preview flow for bundle=%s", bundle_key)

        display_name = self._display_names.get(bundle_key, bundle_key)

        preview_data, dummy_data = self._preview_gen.generate(
            session_id, bundle_key, extracted
        )

        payload = self._app_gen.assemble(
            session_id=session_id,
            bundle_key=bundle_key,
            display_name=display_name,
            preview_data=preview_data,
            dummy_data=dummy_data,
        )
        session_logger.info("Preview flow complete for session=%s", session_id)
        return payload
