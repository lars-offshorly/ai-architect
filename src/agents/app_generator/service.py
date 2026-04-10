from __future__ import annotations

from typing import cast

from catalog.bundle_catalog import BundleCatalog
from core.logging import get_logger, get_session_logger
from domain.models.app_payload import AppPayload
from repositories.template_repository import TemplateRepository

from .contract import AppPayloadContract
from .formatter import AppPayloadFormatter
from .config_assembly import map_relationships
from .schemas import DummyDataJsonSchema, GenerationJsonSchema
from .validators import validate_dummy_data_json, validate_generation_json

logger = get_logger(__name__)


class AppGeneratorService:
    def __init__(
        self, template_repo: TemplateRepository, catalog: BundleCatalog
    ) -> None:
        self._repo = template_repo
        self._catalog = catalog
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

        bundle = self._catalog.get(bundle_key)
        if bundle is None:
            # Fallback to the key itself if not in catalog (unlikely for confirmed session)
            template_dir = bundle_key
            render_key = bundle_key
            entity_definitions = {}
        else:
            template_dir = bundle.template_dir
            render_key = bundle.render_key
            entity_definitions = (
                bundle.metadata.entity_definitions if bundle.metadata else {}
            )

        # Load from the correct directory resolved from the catalog
        generation_json = self._repo.load_app_json(template_dir)
        generation_json["session_id"] = session_id
        # Ensure the payload uses the render key per AD-2
        generation_json["bundle_key"] = render_key

        # 1. Legacy structural validation
        validate_generation_json(generation_json, bundle_key)
        validate_dummy_data_json(dummy_data, bundle_key)

        # 1a. Inject relationship map into config
        if entity_definitions:
            relationships = map_relationships(render_key, entity_definitions)
            config = generation_json.get("config")
            if isinstance(config, dict):
                config["relationships"] = [r.model_dump() for r in relationships]
                session_logger.debug(
                    "Mapped %d relationships for bundle=%s", len(relationships), render_key
                )

        # 2. Strict Pydantic Schema Validation (Integrated from T140)
        # This ensures config and stores sub-schemas are 100% correct.
        GenerationJsonSchema.model_validate(generation_json)
        DummyDataJsonSchema.model_validate(
            {
                "schema_version": generation_json.get("schema_version", "1.0"),
                "bundle_key": render_key,
                "session_id": session_id,
                "stores": dummy_data.get("stores", {}),
            }
        )

        # 3. Contract check
        contract = AppPayloadContract(
            schema_version=str(generation_json.get("schema_version", "1.0")),
            session_id=session_id,
            bundle_key=render_key,
            display_name=display_name,
            modules=list(cast(list[object], generation_json.get("modules", []))),
            generation_json=generation_json,
            dummy_data_json=dummy_data,
            has_entity_definitions=bool(entity_definitions),
        )
        errors = contract.validate_contract()
        if errors:
            session_logger.warning("Contract validation warnings: %s", errors)

        payload = self._formatter.format(
            session_id=session_id,
            bundle_key=render_key,
            display_name=display_name,
            generation_json=generation_json,
            dummy_data_json=dummy_data,
        )
        session_logger.info("App payload assembled for session=%s", session_id)
        return payload
