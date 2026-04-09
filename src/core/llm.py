from __future__ import annotations

from langchain_openai import ChatOpenAI

from .config import get_settings


def get_openai_chat_model(*, temperature: float = 0.0) -> ChatOpenAI:
    settings = get_settings()
    model_name = settings.OPENAI_MODEL.strip()
    if not model_name:
        raise RuntimeError("OPENAI_MODEL is not configured.")
    return ChatOpenAI(model=model_name, temperature=temperature)
