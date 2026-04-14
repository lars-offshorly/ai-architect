from __future__ import annotations

from typing import cast

from catalog.bundle_catalog import BundleCatalog
from core.logging import get_logger, get_session_logger
from domain.models.app_payload import AppPayload
from repositories.template_repository import TemplateRepository

from .contract import AppPayloadContract
from .formatter import AppPayloadFormatter
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
            # Fallback to the key itself if not in catalog
            # (unlikely for confirmed session)
            template_dir = bundle_key
            render_key = bundle_key
        else:
            template_dir = bundle.template_dir
            render_key = bundle.render_key

        # Load from the correct directory resolved from the catalog
        generation_json = self._repo.load_app_json(template_dir)
        generation_json["session_id"] = session_id
        # Ensure the payload uses the render key per AD-2
        generation_json["bundle_key"] = render_key
        # AD-2 registry owns canonical modules; older app templates may omit them.
        if (
            not isinstance(generation_json.get("modules"), list)
            or not generation_json.get("modules")
        ) and bundle is not None:
            generation_json["modules"] = list(bundle.default_modules)
        normalized_dummy_data = self._normalize_dummy_data(dummy_data)

        # 1. Legacy structural validation
        validate_generation_json(generation_json, render_key)
        validate_dummy_data_json(normalized_dummy_data, render_key)

        # 2. Strict Pydantic Schema Validation (Integrated from T140)
        # This ensures config and stores sub-schemas are 100% correct.
        GenerationJsonSchema.model_validate(generation_json)
        dummy_schema_input = dict(normalized_dummy_data)
        dummy_schema_input.setdefault(
            "schema_version", generation_json.get("schema_version", "1.0")
        )
        dummy_schema_input.setdefault("bundle_key", render_key)
        dummy_schema_input.setdefault("session_id", session_id)
        dummy_schema_input.setdefault("stores", {})
        DummyDataJsonSchema.model_validate(dummy_schema_input)

        # 3. Contract check
        contract = AppPayloadContract(
            schema_version=str(generation_json.get("schema_version", "1.0")),
            session_id=session_id,
            bundle_key=render_key,
            display_name=display_name,
            modules=list(cast(list[object], generation_json.get("modules", []))),
            generation_json=generation_json,
            dummy_data_json=normalized_dummy_data,
        )
        errors = contract.validate_contract()
        if errors:
            session_logger.warning("Contract validation warnings: %s", errors)

        payload = self._formatter.format(
            session_id=session_id,
            bundle_key=render_key,
            display_name=display_name,
            generation_json=generation_json,
            dummy_data_json=normalized_dummy_data,
        )
        session_logger.info("App payload assembled for session=%s", session_id)
        return payload

    @staticmethod
    def _normalize_dummy_data(data: dict[str, object]) -> dict[str, object]:
        """Normalize incoming dummy_data_json before strict schema validation."""
        normalized = dict(data)
        stores = normalized.get("stores")
        if not isinstance(stores, dict):
            return normalized

        kpis = stores.get("kpis")
        if not isinstance(kpis, list):
            return normalized

        normalized_stores = dict(stores)
        normalized_kpis: list[object] = []
        for idx, item in enumerate(kpis, start=1):
            if not isinstance(item, dict):
                normalized_kpis.append(item)
                continue
            kpi = dict(item)
            if not kpi.get("id"):
                key = kpi.get("key")
                kpi["id"] = key if isinstance(key, str) and key else idx
            normalized_kpis.append(kpi)

        normalized_stores["kpis"] = normalized_kpis
        normalized["stores"] = normalized_stores
        return normalized
