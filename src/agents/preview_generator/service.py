from __future__ import annotations

from core.logging import get_logger, get_session_logger
from domain.models.extracted_info import ExtractedInfo
from domain.models.preview_json import PreviewJson
from repositories.template_repository import TemplateRepository

from .dummy_data import DummyDataInjector
from .fetcher import TemplateFetcher
from .modifier import TemplateModifier
from .validators import validate_dummy_data, validate_preview_json

logger = get_logger(__name__)


class PreviewGeneratorService:
    def __init__(self, template_repo: TemplateRepository) -> None:
        self._fetcher = TemplateFetcher(template_repo)
        self._modifier = TemplateModifier()
        self._injector = DummyDataInjector()

    def generate(
        self,
        session_id: str,
        bundle_key: str,
        extracted: ExtractedInfo,
    ) -> tuple[dict[str, object], dict[str, object]]:
        session_logger = get_session_logger(__name__, session_id)
        session_logger.info("Generating preview for bundle=%s", bundle_key)

        raw_preview = self._fetcher.fetch_preview(bundle_key)
        raw_dummy = self._fetcher.fetch_dummy_data(bundle_key)

        preview = self._modifier.inject(raw_preview, extracted)
        dummy = self._injector.inject(raw_dummy, extracted)

        validate_preview_json(preview, bundle_key)
        validate_dummy_data(dummy, bundle_key)

        session_logger.info("Preview generation complete for bundle=%s", bundle_key)
        return preview, dummy

    def to_preview_model(
        self,
        bundle_key: str,
        display_name: str,
        preview_data: dict[str, object],
    ) -> PreviewJson:
        stores = preview_data.get("stores")
        modules = preview_data.get("modules")
        return PreviewJson(
            session_id=str(preview_data.get("session_id", "")),
            bundle_key=bundle_key,
            display_name=display_name,
            modules=modules if isinstance(modules, list) else [],
            stores=stores if isinstance(stores, dict) else {},
        )
