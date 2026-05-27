from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

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
    monkeypatch.setenv("DEV_BYPASS", "true")

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
# ---------------------------------------------------------------------------
# Note: shared_catalog (BundleCatalog, session-scoped) is defined in
# tests/conftest.py and cascades into all integration tests automatically.
# ---------------------------------------------------------------------------


class FakeManifestProvider:
    """In-memory manifest stub for integration tests.
    Provides TenantProvisioningManifest dicts by bundle key without hitting
    the CanonicalManifestRegistry or the LLM.
    """

    def __init__(self, manifests: dict[str, dict[str, Any]]) -> None:
        self._manifests = manifests

    def get(self, bundle_key: str) -> dict[str, Any] | None:
        return self._manifests.get(bundle_key)

    def has(self, bundle_key: str) -> bool:
        return bundle_key in self._manifests


def _load_jsonc(path: Path) -> dict[str, Any]:
    return json.loads(re.sub(r"//[^\n]*", "", path.read_text(encoding="utf-8")))


@pytest.fixture
def fake_manifest_provider() -> FakeManifestProvider:
    """Return a FakeManifestProvider loaded with ticketing and construction fixtures."""
    samples = Path(__file__).resolve().parents[2] / "new_json_samples"
    return FakeManifestProvider({
        "ticketing": _load_jsonc(samples / "tenant_provisioning_bpo.jsonc"),
        "construction": _load_jsonc(samples / "tenant_provisioning_construction.jsonc"),
    })

