from pathlib import Path

import pytest

from agents.preview_generator.bundle_template_loader import BundleTemplateLoader
from catalog.bundle_catalog import BundleCatalog
from core.config import get_settings


@pytest.fixture(scope="session")
def shared_catalog() -> BundleCatalog:
    """Return a session-scoped BundleCatalog instance."""
    settings = get_settings()
    return BundleCatalog(Path(settings.BUNDLE_REGISTRY_PATH))


@pytest.fixture(scope="session")
def shared_template_loader() -> BundleTemplateLoader:
    """Return a session-scoped BundleTemplateLoader instance."""
    return BundleTemplateLoader()
