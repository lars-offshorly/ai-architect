"""FastAPI dependency providers for repositories, services, and orchestrators."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from langchain_openai import ChatOpenAI

from agents.app_generator.mock_builder import MockPayloadBuilder
from agents.app_generator.service import AppGeneratorService
from agents.interpreter.service import InterpreterService
from agents.preview_generator.bundle_template_loader import BundleTemplateLoader
from agents.preview_generator.dashboard.templates import (
    DashboardTemplateRegistry,
)
from agents.preview_generator.service import PreviewGeneratorService
from agents.replier.service import ReplierService
from catalog.bundle_catalog import BundleCatalog
from core.config import get_settings
from domain.services.bundle_metadata import BundleMetadataService
from orchestrators.conversation_flow import ConversationFlow
from orchestrators.preview_flow import PreviewFlow
from repositories.conversation_repository import ConversationRepository
from repositories.session_repository import SessionRepository
from repositories.template_repository import TemplateRepository


@lru_cache(maxsize=1)
def get_bundle_catalog() -> BundleCatalog:
    """Return a cached BundleCatalog instance.

    Cache is process-scoped; dev server restarts clear it.
    """
    settings = get_settings()
    catalog = BundleCatalog(Path(settings.BUNDLE_REGISTRY_PATH))
    if not settings.SKIP_CATALOG_VALIDATION:
        templates_dir = Path(settings.TEMPLATES_DIR)
        catalog.validate(templates_dir=templates_dir)
        catalog.validate_template_consistency(templates_dir=templates_dir)
    return catalog


@lru_cache(maxsize=1)
def get_template_repository() -> TemplateRepository:
    """Return a cached TemplateRepository pointed at the configured templates dir."""
    settings = get_settings()
    return TemplateRepository(Path(settings.TEMPLATES_DIR))


@lru_cache(maxsize=1)
def get_session_repository() -> SessionRepository:
    """Return a cached in-memory SessionRepository."""
    return SessionRepository()


@lru_cache(maxsize=1)
def get_conversation_repository() -> ConversationRepository:
    """Return a cached in-memory ConversationRepository."""
    return ConversationRepository()


@lru_cache(maxsize=1)
def get_interpreter_service() -> InterpreterService:
    """Return a cached InterpreterService seeded with all known bundle keys."""
    settings = get_settings()
    catalog = get_bundle_catalog()

    if settings.DISABLE_LLM_CALLS:
        model = None
        summarizer_model = None
    else:
        model = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            temperature=settings.CLASSIFIER_TEMPERATURE,
            api_key=settings.OPENAI_API_KEY,
        )
        summarizer_model = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            temperature=settings.CONVERSATIONAL_TEMPERATURE,
            api_key=settings.OPENAI_API_KEY,
        )

    return InterpreterService(
        bundle_keys=catalog.list_keys(),
        catalog=catalog,
        model=model,
        summarizer_model=summarizer_model,
    )


@lru_cache(maxsize=1)
def get_replier_service() -> ReplierService:
    """Return a cached ReplierService wired to the bundle catalog."""
    return ReplierService(catalog=get_bundle_catalog())


@lru_cache(maxsize=1)
def get_preview_generator_service() -> PreviewGeneratorService:
    """Return a cached PreviewGeneratorService."""
    return PreviewGeneratorService(get_bundle_catalog())


@lru_cache(maxsize=1)
def get_app_generator_service() -> AppGeneratorService:
    """Return a cached AppGeneratorService backed by the template repository."""
    return AppGeneratorService(get_template_repository(), get_bundle_catalog())


@lru_cache(maxsize=1)
def get_conversation_flow() -> ConversationFlow:
    """Return a cached ConversationFlow wired to interpreter and replier services."""
    catalog = get_bundle_catalog()
    required_slots = {b.bundle_key: b.required_slots for b in catalog.list_all()}
    return ConversationFlow(
        interpreter_service=get_interpreter_service(),
        replier_service=get_replier_service(),
        bundle_catalog=catalog,
        required_slots_by_bundle=required_slots,
    )


@lru_cache(maxsize=1)
def get_bundle_template_loader() -> BundleTemplateLoader:
    """Return a cached BundleTemplateLoader for static app-0*.json variants."""
    return BundleTemplateLoader()


@lru_cache(maxsize=1)
def get_dashboard_template_registry() -> DashboardTemplateRegistry:
    """Return a cached DashboardTemplateRegistry backed by dashboard_output_templates/."""
    return DashboardTemplateRegistry(catalog=get_bundle_catalog())


@lru_cache(maxsize=1)
def get_preview_flow() -> PreviewFlow:
    """Return a cached PreviewFlow wired to the preview generator service."""
    catalog = get_bundle_catalog()
    display_names = {b.bundle_key: b.display_name for b in catalog.list_all()}
    return PreviewFlow(
        preview_generator_service=get_preview_generator_service(),
        bundle_display_names=display_names,
        bundle_template_loader=get_bundle_template_loader(),
        static_dashboard_outputs=get_dashboard_template_registry(),
    )


@lru_cache(maxsize=1)
def get_bundle_metadata_service() -> BundleMetadataService:
    """Return metadata service backed by the cached bundle catalog."""
    return BundleMetadataService(get_bundle_catalog())


@lru_cache(maxsize=1)
def get_mock_payload_builder() -> MockPayloadBuilder:
    """Return a cached MockPayloadBuilder backed by the preview generator pipeline."""
    import json
    import pathlib

    mocks_path = pathlib.Path(__file__).parent.parent.parent / "docs" / "api-mocks.json"
    service_mocks: dict = {}
    if mocks_path.exists():
        with mocks_path.open(encoding="utf-8") as f:
            service_mocks = json.load(f)
    return MockPayloadBuilder(
        preview_service=get_preview_generator_service(),
        catalog=get_bundle_catalog(),
        service_mocks=service_mocks,
    )
