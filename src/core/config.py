from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-5-mini"

    PORT: int = Field(default=8000, ge=1, le=65535)
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    CLASSIFIER_TEMPERATURE: float = Field(default=0.0, ge=0.0, le=1.0)
    CONVERSATIONAL_TEMPERATURE: float = Field(default=0.3, ge=0.0, le=1.0)
    ASSEMBLER_TEMPERATURE: float = Field(default=0.2, ge=0.0, le=1.0)

    CONFIDENCE_THRESHOLD: float = Field(default=0.6, ge=0.0, le=1.0)
    TOP_K_BUNDLES: int = Field(default=3, ge=1)

    CONFIDENCE_PROCEED_THRESHOLD: float = Field(default=0.75, ge=0.0, le=1.0)
    CONFIDENCE_SUGGEST_THRESHOLD: float = Field(default=0.50, ge=0.0, le=1.0)
    SCORE_GAP_MINIMUM: float = Field(default=0.15, ge=0.0, le=1.0)
    # Cap clarifications at 3 by default. The v2 canonical manifest only needs a
    # tiny tenant header (industry, company, size, region), but giving the user
    # a few rounds to specify it before we fall back to a generic bundle keeps
    # the conversation feeling cooperative rather than tripping into a generic
    # baseline after the first miss.
    MAX_CLARIFICATION_TURNS: int = Field(default=3, ge=1)

    TEMPLATES_DIR: str = "src/templates/bundles"
    BUNDLE_REGISTRY_PATH: str = "src/templates/bundle_registry.yaml"
    CANONICAL_MANIFESTS_DIR: str = "new_json_samples"
    CANONICAL_STRICT_INDUSTRY_MAPPING: bool = True
    CANONICAL_ALLOW_REGISTRY_MODULE_FALLBACK: bool = False

    REDIS_URL: str = "redis://localhost:6379/0"
    DEV_BYPASS: bool = False
    RATE_LIMIT_PER_MINUTE: int = 60
    ENABLE_RATE_LIMIT: bool = True

    DISABLE_LLM_CALLS: bool = False
    DISABLE_DASHBOARD_CALLS: bool = False
    SKIP_CATALOG_VALIDATION: bool = False
    EDIT_LLM_FALLBACK_ENABLED: bool = False
    EDIT_LLM_TIMEOUT_MS: int = Field(default=1200, ge=100, le=10000)
    EDIT_LLM_MAX_RETRIES: int = Field(default=1, ge=0, le=3)
    EDIT_LLM_CB_THRESHOLD: int = Field(default=3, ge=1, le=20)
    EDIT_LLM_CB_COOLDOWN_SEC: int = Field(default=30, ge=1, le=600)
    MAX_APP_MANIFEST_BYTES: int = Field(default=200_000, ge=10_000, le=5_000_000)
    MAX_EDIT_PREVIEW_BYTES: int = Field(default=400_000, ge=10_000, le=10_000_000)

    SENTRY_DSN: str = ""
    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_PROJECT: str = "ai-architect"

    @field_validator("DEBUG", mode="before")
    @classmethod
    def _coerce_debug(cls, value: object) -> object:
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"release", "prod", "production"}:
                return False
            if lowered in {"debug", "dev", "development"}:
                return True
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
