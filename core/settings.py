from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4.1"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_EMBEDDING_DIMENSIONS: int = 1536

    PINECONE_API_KEY: str = ""
    PINECONE_INDEX: str = ""
    PINECONE_HOST: str = ""
    PINECONE_BUNDLE_TEMPLATES_NAMESPACE: str = "bundle_templates"

    DATABASE_URL: str = ""
    DB_POOL_MAX_SIZE: int = 20

    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    CLASSIFIER_TEMPERATURE: float = 0.0
    CONVERSATIONAL_TEMPERATURE: float = 0.3
    ASSEMBLER_TEMPERATURE: float = 0.2

    JWT_SECRET: str = ""
    JWT_ALGORITHM: str = "HS256"
    RATE_LIMIT_PER_MINUTE: int = 60

    SENTRY_DSN: str = ""
    
    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_PROJECT: str = "ai-architect"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    if settings.LANGCHAIN_TRACING_V2 and settings.LANGCHAIN_API_KEY:
        import os
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY
        os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT
    return settings
