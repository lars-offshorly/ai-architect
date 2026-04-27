import pytest
import api.deps as deps


def pytest_collection_modifyitems(items):
    """Automatically mark tests in tests/integration as integration tests."""
    for item in items:
        if "tests/integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)


@pytest.fixture(autouse=True)
def disable_external_calls(monkeypatch):
    """Automatically disable all external HTTP calls for integration tests."""
    monkeypatch.setenv("DISABLE_LLM_CALLS", "true")
    monkeypatch.setenv("DISABLE_DASHBOARD_CALLS", "true")
    monkeypatch.setenv("SKIP_CATALOG_VALIDATION", "true")

    # Also clear lru_cache so settings reload with new env vars
    deps.get_settings.cache_clear()
    deps.get_interpreter_service.cache_clear()
    deps.get_bundle_catalog.cache_clear()
    deps.get_preview_flow.cache_clear()

    yield

    # Teardown: clear caches again to avoid cross-test contamination
    deps.get_settings.cache_clear()
    deps.get_interpreter_service.cache_clear()
    deps.get_bundle_catalog.cache_clear()
    deps.get_preview_flow.cache_clear()
