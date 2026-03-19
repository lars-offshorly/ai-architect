"""
Factory module for creating LLM instances with consistent configuration.
"""

from __future__ import annotations

from typing import Optional

from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from .settings import get_settings


def get_openai_chat_model(
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    **kwargs: object,
) -> ChatOpenAI:
    """
    Factory function to create a ChatOpenAI instance with default configuration.

    This centralizes the ChatOpenAI initialization to reduce code duplication
    and ensure consistent configuration across all orchestrator nodes.

    Args:
        model: Model name override. Defaults to settings.OPENAI_MODEL.
        temperature: Temperature override. Defaults to model default
            (None means use LangChain default).
        **kwargs: Additional arguments passed to ChatOpenAI constructor.

    Returns:
        Configured ChatOpenAI instance.

    Example:
        # Basic usage (uses all defaults from settings)
        model = get_openai_chat_model()

        # With temperature override for deterministic output
        model = get_openai_chat_model(temperature=0)

        # With custom model
        model = get_openai_chat_model(model="gpt-4.1-mini")
    """
    settings = get_settings()
    model_name = model or settings.OPENAI_MODEL
    api_key = SecretStr(settings.OPENAI_API_KEY)

    init_kwargs: dict[str, object] = {
        "model": model_name,
        "api_key": api_key,
        **kwargs,
    }

    if temperature is not None:
        init_kwargs["temperature"] = temperature

    return ChatOpenAI(**init_kwargs)
