from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4.1"

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
    MAX_CLARIFICATION_TURNS: int = Field(default=3, ge=1)

    TEMPLATES_DIR: str = "src/templates/bundles"
    BUNDLE_REGISTRY_PATH: str = "src/templates/bundle_registry.yaml"

    JWT_SECRET: str = ""
    JWT_ALGORITHM: str = "HS256"
    RATE_LIMIT_PER_MINUTE: int = 60

    ENABLE_MOCK_ENDPOINTS: bool = False

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
