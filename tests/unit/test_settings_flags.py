import os
from unittest.mock import patch

import pytest

import api.deps as deps
from core.config import get_settings


@pytest.fixture(autouse=True)
def clean_settings_cache():
    """Ensure settings and dependency caches are cleared before and after each test."""
    # Clear before
    deps.get_settings.cache_clear()
    deps.get_interpreter_service.cache_clear()
    deps.get_bundle_catalog.cache_clear()
    deps.get_preview_flow.cache_clear()

    yield

    # Clear after
    deps.get_settings.cache_clear()
    deps.get_interpreter_service.cache_clear()
    deps.get_bundle_catalog.cache_clear()
    deps.get_preview_flow.cache_clear()

def test_settings_flags_default_to_false():
    """Verify that the new CI speedup flags default to False."""
    # Ensure env vars are not set
    os.environ.pop("DISABLE_LLM_CALLS", None)
    os.environ.pop("DISABLE_DASHBOARD_CALLS", None)
    os.environ.pop("SKIP_CATALOG_VALIDATION", None)
    
    settings = get_settings()
    assert settings.DISABLE_LLM_CALLS is False
    assert settings.DISABLE_DASHBOARD_CALLS is False
    assert settings.SKIP_CATALOG_VALIDATION is False

def test_settings_flags_from_env(monkeypatch):
    """Verify that settings flags can be overridden via environment variables."""
    monkeypatch.setenv("DISABLE_LLM_CALLS", "true")
    monkeypatch.setenv("DISABLE_DASHBOARD_CALLS", "true")
    monkeypatch.setenv("SKIP_CATALOG_VALIDATION", "true")
    
    settings = get_settings()
    
    assert settings.DISABLE_LLM_CALLS is True
    assert settings.DISABLE_DASHBOARD_CALLS is True
    assert settings.SKIP_CATALOG_VALIDATION is True

@pytest.mark.asyncio
async def test_get_interpreter_service_when_llm_disabled(monkeypatch):
    """When LLM is disabled, interpreter still routes through the canonical
    resolver. The user message hits a canonical industry alias and resolves
    to the mapped bundle without invoking any classifier."""
    monkeypatch.setenv("DISABLE_LLM_CALLS", "true")

    service = deps.get_interpreter_service()

    from domain.models.interpreter_request import InterpreterRequest

    request = InterpreterRequest(
        session_id="test-session",
        user_message="I need a recruitment platform for our hiring agency",
        history=[],
    )
    extracted, suggested = await service.interpret(request)

    assert extracted.session_id == "test-session"
    assert suggested.selected_bundle is not None
    assert suggested.selected_bundle.bundle_key == "hr_management"
    assert suggested.confidence_status == "proceed"

    # Summarization is safely no-op without LLM model wiring
    summary = await service.summarize_history("test-session", history=[])
    assert summary == ""

def test_get_bundle_catalog_respects_skip_validation(monkeypatch):
    """Verify catalog validation is skipped when configured."""
    monkeypatch.setenv("SKIP_CATALOG_VALIDATION", "true")

    with (
        patch("catalog.bundle_catalog.BundleCatalog.validate") as mock_validate,
        patch(
            "catalog.bundle_catalog.BundleCatalog.validate_template_consistency"
        ) as mock_consistency,
    ):

        catalog = deps.get_bundle_catalog()
        assert catalog is not None
        mock_validate.assert_not_called()
        mock_consistency.assert_not_called()
