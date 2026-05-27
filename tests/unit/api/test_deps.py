from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from api import deps


def test_get_bundle_catalog_runs_catalog_validator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deps.get_bundle_catalog.cache_clear()
    fake_catalog = MagicMock()
    fake_bundle_catalog_cls = MagicMock(return_value=fake_catalog)

    monkeypatch.setattr(deps, "BundleCatalog", fake_bundle_catalog_cls)
    monkeypatch.setattr(
        deps,
        "get_settings",
        lambda: SimpleNamespace(
            BUNDLE_REGISTRY_PATH="tmp/registry.yaml",
            SKIP_CATALOG_VALIDATION=False,
        ),
    )

    deps.get_bundle_catalog()

    fake_bundle_catalog_cls.assert_called_once_with(Path("tmp/registry.yaml"))
    fake_catalog.validate.assert_called_once_with()
    fake_catalog.validate_template_consistency.assert_not_called()
    deps.get_bundle_catalog.cache_clear()
