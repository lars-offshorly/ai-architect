from __future__ import annotations

from core.constants import APP_PAYLOAD_SCHEMA_VERSION
from core.logging import get_logger
from domain.models.app_payload import AppPayload

logger = get_logger(__name__)


class AppPayloadFormatter:
    def format(
        self,
        session_id: str,
        bundle_key: str,
        display_name: str,
        generation_json: dict[str, object],
        dummy_data_json: dict[str, object],
        v2_manifest: dict[str, object] | None = None,
    ) -> AppPayload:
        modules = generation_json.get("modules")
        payload = AppPayload(
            schema_version=APP_PAYLOAD_SCHEMA_VERSION,
            session_id=session_id,
            bundle_key=bundle_key,
            display_name=display_name,
            modules=modules if isinstance(modules, list) else [],
            generation_json=generation_json,
            dummy_data_json=dummy_data_json,
            v2_manifest=v2_manifest,
        )
        logger.info(
            "App payload formatted for session=%s bundle=%s", session_id, bundle_key
        )
        return payload
