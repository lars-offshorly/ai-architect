"""FastAPI dependency providers for repositories, services, and orchestrators."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from langchain_openai import ChatOpenAI

from agents.interpreter.llm_industry_classifier import LLMIndustryClassifier
from agents.interpreter.service import InterpreterService
from agents.preview_generator.service import PreviewGeneratorService
from agents.replier.service import ReplierService
from agents.tenant_provisioning.service import TenantProvisioningService
from catalog.bundle_catalog import BundleCatalog
from core.config import get_settings
from domain.services.canonical_bundle_resolver import CanonicalBundleResolver
from domain.services.canonical_manifest_registry import CanonicalManifestRegistry
from domain.services.canonical_metadata_service import CanonicalMetadataService
from domain.services.canonical_payload_builder import CanonicalPayloadBuilder
from domain.services.registry_facade import RegistryFacade
from orchestrators.conversation_flow import ConversationFlow
from orchestrators.preview_flow import PreviewFlow
from repositories.conversation_repository import ConversationRepository
from repositories.session_repository import SessionRepository


@lru_cache(maxsize=1)
def get_bundle_catalog() -> BundleCatalog:
    """Return a cached BundleCatalog instance.

    Cache is process-scoped; dev server restarts clear it.
    """
    settings = get_settings()
    catalog = BundleCatalog(Path(settings.BUNDLE_REGISTRY_PATH))
    if not settings.SKIP_CATALOG_VALIDATION:
        catalog.validate()
    return catalog


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
    """Return a cached InterpreterService wired for canonical runtime selection."""
    settings = get_settings()
    registry_facade = get_registry_facade()

    if settings.DISABLE_LLM_CALLS:
        model = None
        summarizer_model = None
        llm_industry_classifier: LLMIndustryClassifier | None = None
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
        llm_industry_classifier = LLMIndustryClassifier(
            model=model,
            industry_map=registry_facade.industry_bundle_map(),
            min_confidence=settings.CONFIDENCE_SUGGEST_THRESHOLD,
        )

    return InterpreterService(
        bundle_keys=registry_facade.list_supported_bundles(),
        registry_facade=registry_facade,
        model=model,
        summarizer_model=summarizer_model,
        llm_industry_classifier=llm_industry_classifier,
    )


@lru_cache(maxsize=1)
def get_replier_service() -> ReplierService:
    """Return a cached ReplierService wired to the bundle catalog."""
    return ReplierService()


@lru_cache(maxsize=1)
def get_preview_generator_service() -> PreviewGeneratorService:
    """Return a cached PreviewGeneratorService."""
    return PreviewGeneratorService(get_bundle_catalog())


@lru_cache(maxsize=1)
def get_edit_llm_model() -> ChatOpenAI | None:
    """Return cached model for edit parser fallback, if enabled."""
    settings = get_settings()
    if settings.DISABLE_LLM_CALLS or not settings.EDIT_LLM_FALLBACK_ENABLED:
        return None
    return ChatOpenAI(
        model=settings.OPENAI_MODEL,
        temperature=0.0,
        api_key=settings.OPENAI_API_KEY,
    )


@lru_cache(maxsize=1)
def get_conversation_flow() -> ConversationFlow:
    """Return a cached ConversationFlow wired to interpreter and replier services."""
    required_slots: dict[str, list[str]] = {}
    return ConversationFlow(
        interpreter_service=get_interpreter_service(),
        replier_service=get_replier_service(),
        required_slots_by_bundle=required_slots,
        registry_facade=get_registry_facade(),
    )


@lru_cache(maxsize=1)
def get_tenant_provisioning_service() -> TenantProvisioningService:
    """Return cached tenant provisioning service with baseline selection."""
    return TenantProvisioningService.with_baseline(
        registry_facade=get_registry_facade()
    )


@lru_cache(maxsize=1)
def get_preview_flow() -> PreviewFlow:
    """Return a cached PreviewFlow wired to the preview generator service."""
    catalog = get_bundle_catalog()
    display_names = {b.bundle_key: b.display_name for b in catalog.list_all()}
    return PreviewFlow(
        preview_generator_service=get_preview_generator_service(),
        bundle_display_names=display_names,
        tenant_provisioning_service=get_tenant_provisioning_service(),
    )


@lru_cache(maxsize=1)
def get_registry_facade() -> RegistryFacade:
    """Return canonical registry facade used by runtime entrypoints."""
    settings = get_settings()
    registry = CanonicalManifestRegistry(settings.CANONICAL_MANIFESTS_DIR)
    resolver = CanonicalBundleResolver(
        registry=registry,
        strict_mapping=settings.CANONICAL_STRICT_INDUSTRY_MAPPING,
    )
    payload_builder = CanonicalPayloadBuilder(registry)
    metadata_service = CanonicalMetadataService(registry)
    return RegistryFacade(
        resolver=resolver,
        payload_builder=payload_builder,
        metadata_service=metadata_service,
        catalog_fallback=(
            get_bundle_catalog()
            if settings.CANONICAL_ALLOW_REGISTRY_MODULE_FALLBACK
            else None
        ),
        allow_registry_module_fallback=(
            settings.CANONICAL_ALLOW_REGISTRY_MODULE_FALLBACK
        ),
    )
