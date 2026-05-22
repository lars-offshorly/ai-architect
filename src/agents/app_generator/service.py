from __future__ import annotations

from catalog.bundle_catalog import BundleCatalog
from core.logging import get_session_logger
from domain.models.app_payload import AppPayload
from repositories.template_repository import TemplateRepository

from .contract import AppPayloadContract
from .formatter import AppPayloadFormatter
from .validators import validate_manifest


class AppGeneratorService:
    """v2-only payload assembler."""

    def __init__(self, template_repo: TemplateRepository, catalog: BundleCatalog) -> None:
        self._repo = template_repo
        self._catalog = catalog
        self._formatter = AppPayloadFormatter()

    def assemble(
        self,
        session_id: str,
        bundle_key: str,
        display_name: str,
        manifest: dict[str, object],
        modules: list[str] | None = None,
    ) -> AppPayload:
        session_logger = get_session_logger(__name__, session_id)
        validate_manifest(manifest)

        contract = AppPayloadContract(
            schema_version="2.0",
            session_id=session_id,
            bundle_key=bundle_key,
            display_name=display_name,
            modules=modules or [],
            manifest=manifest,
        )
        errors = contract.validate_contract()
        if errors:
            session_logger.warning("Contract validation warnings: %s", errors)

        return self._formatter.format(
            session_id=session_id,
            bundle_key=bundle_key,
            display_name=display_name,
            modules=modules or [],
            manifest=manifest,
        )
