"""Dashboard template registry.

Loads dashboard templates from the ``dashboard_templates/`` directory and
resolves the correct template for a given bundle key.

Templates are loaded once on first access and cached for the process lifetime.
Adding support for a new bundle requires only dropping a new ``.json`` file
into ``dashboard_templates/`` and adding a mapping entry to
``_BUNDLE_TO_TEMPLATE``.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from core.logging import get_logger

logger = get_logger(__name__)

# Map from catalog/registry bundle key → template filename (without .json).
# Tier 3 bundles (finance, marketing, sales, …) have no entry and will
# receive None from get(), skipping the dashboard call entirely.
_BUNDLE_TO_TEMPLATE: dict[str, str] = {
    "hr_management": "hr_management",
    "hr_hub": "hr_management",  # render key alias
    "project_mgmt": "project_management",
}

_DEFAULT_TEMPLATES_DIR = Path(__file__).parents[5] / "dashboard_templates"


class DashboardTemplateRegistry:
    """Resolves and returns deep-copied dashboard template dicts by bundle key.

    Deep copies are returned so callers (the personalizer) can safely mutate
    them without affecting the cached originals.
    """

    def __init__(self, templates_dir: Path = _DEFAULT_TEMPLATES_DIR) -> None:
        self._dir = templates_dir
        self._cache: dict[str, dict] = {}
        self._load_all()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, bundle_key: str) -> dict | None:
        """Return a deep copy of the template for ``bundle_key``, or None."""
        filename = _BUNDLE_TO_TEMPLATE.get(bundle_key)
        if filename is None:
            return None
        template = self._cache.get(filename)
        if template is None:
            return None
        return copy.deepcopy(template)

    def supported_bundles(self) -> list[str]:
        """Return the bundle keys that have a registered template."""
        return list(_BUNDLE_TO_TEMPLATE.keys())

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load_all(self) -> None:
        """Load every template referenced by ``_BUNDLE_TO_TEMPLATE`` at init."""
        filenames = set(_BUNDLE_TO_TEMPLATE.values())
        for filename in filenames:
            path = self._dir / f"{filename}.json"
            if not path.exists():
                logger.warning(
                    "Dashboard template not found: %s — "
                    "bundle(s) using it will skip dashboard enrichment",
                    path,
                )
                continue
            try:
                with path.open(encoding="utf-8") as f:
                    self._cache[filename] = json.load(f)
                logger.info("Loaded dashboard template: %s", path.name)
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning(
                    "Failed to load dashboard template %s: %s", path.name, exc
                )
