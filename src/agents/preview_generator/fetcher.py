from __future__ import annotations

from core.exceptions import BundleNotFoundError
from core.logging import get_logger
from repositories.template_repository import TemplateRepository

logger = get_logger(__name__)


class TemplateFetcher:
    def __init__(self, template_repo: TemplateRepository) -> None:
        self._repo = template_repo

    def fetch_preview(self, bundle_key: str) -> dict[str, object]:
        self._assert_bundle_exists(bundle_key)
        data = self._repo.load_preview_json(bundle_key)
        logger.info("Fetched preview template for bundle=%s", bundle_key)
        return data

    def fetch_app(self, bundle_key: str) -> dict[str, object]:
        self._assert_bundle_exists(bundle_key)
        data = self._repo.load_app_json(bundle_key)
        logger.info("Fetched app template for bundle=%s", bundle_key)
        return data

    def fetch_dummy_data(self, bundle_key: str) -> dict[str, object]:
        self._assert_bundle_exists(bundle_key)
        data = self._repo.load_dummy_data(bundle_key)
        logger.info("Fetched dummy data template for bundle=%s", bundle_key)
        return data

    def _assert_bundle_exists(self, bundle_key: str) -> None:
        if not self._repo.bundle_exists(bundle_key):
            raise BundleNotFoundError(bundle_key)
