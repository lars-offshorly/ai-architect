from pathlib import Path

import pytest

from catalog.bundle_catalog import BundleCatalog
from core.config import get_settings
from domain.services.canonical_manifest_registry import CanonicalManifestRegistry
from domain.services.canonical_validation import (
    EmployeeMutableFieldsSpec,
    ReferentialIntegritySpec,
    UniqueIdsSpec,
    ValidationChain,
)


@pytest.fixture(scope="session")
def shared_catalog() -> BundleCatalog:
    """Return a session-scoped BundleCatalog instance."""
    settings = get_settings()
    return BundleCatalog(Path(settings.BUNDLE_REGISTRY_PATH))


@pytest.fixture(scope="session", autouse=True)
def validate_canonical_manifests_before_tests() -> None:
    """CI gate: canonical manifests must validate before tests execute."""
    root = Path(__file__).resolve().parents[1]
    registry = CanonicalManifestRegistry(root / "new_json_samples")
    manifests = registry.load_all()
    registry.validate_mapping_coverage()
    ValidationChain(
        specs=(UniqueIdsSpec(), ReferentialIntegritySpec(), EmployeeMutableFieldsSpec())
    ).validate_all(manifests)
