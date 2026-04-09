from __future__ import annotations

from typing import cast

from core.logging import get_logger, get_session_logger
from domain.models.app_payload import AppPayload
from repositories.template_repository import TemplateRepository

from .contract import AppPayloadContract
from .formatter import AppPayloadFormatter
from .validators import validate_dummy_data_json, validate_generation_json

logger = get_logger(__name__)


class AppGeneratorService:
    def __init__(self, template_repo: TemplateRepository) -> None:
        self._repo = template_repo
        self._formatter = AppPayloadFormatter()

    def assemble(
        self,
        session_id: str,
        bundle_key: str,
        display_name: str,
        dummy_data: dict[str, object],
    ) -> AppPayload:
        session_logger = get_session_logger(__name__, session_id)
        session_logger.info("Assembling app payload for bundle=%s", bundle_key)

        generation_json = self._repo.load_app_json(bundle_key)
        generation_json["session_id"] = session_id

        validate_generation_json(generation_json, bundle_key)
        validate_dummy_data_json(dummy_data, bundle_key)

        contract = AppPayloadContract(
            schema_version=str(generation_json.get("schema_version", "1.0")),
            session_id=session_id,
            bundle_key=bundle_key,
            display_name=display_name,
            modules=list(cast(list[object], generation_json.get("modules", []))),
            generation_json=generation_json,
            dummy_data_json=dummy_data,
        )
        errors = contract.validate_contract()
        if errors:
            session_logger.warning("Contract validation warnings: %s", errors)

        payload = self._formatter.format(
            session_id=session_id,
            bundle_key=bundle_key,
            display_name=display_name,
            generation_json=generation_json,
            dummy_data_json=dummy_data,
        )
        session_logger.info("App payload assembled for session=%s", session_id)
        return payload
