"""Dashboard template registry.

Loads dashboard templates from the ``dashboard_templates/`` directory and
resolves the correct template for a (bundle_key, variant_key) pair.

Resolution
----------
1. If ``variant_key`` is given and the bundle's registry entry has a
   ``BundleVariantDefinition`` with a matching ``key``, the variant's
   ``dashboard_template`` filename is used.
2. Otherwise, the bundle's default variant (``is_default: true``) is used.
3. If the bundle has no variants, ``_BUNDLE_TO_TEMPLATE`` is consulted as a
   legacy fallback — this keeps single-template industry bundles working
   until they are migrated to variants.

Templates are loaded once at construction time and cached for the process
lifetime. Deep copies are returned so callers (the personalizer) can mutate
them without affecting the cached originals.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from catalog.bundle_catalog import BundleCatalog
from core.logging import get_logger

logger = get_logger(__name__)

# Legacy fallback mapping for bundles that do not yet declare ``variants`` in
# the registry YAML. Keep this in sync with registry aliases; multi-variant
# bundles should drive selection through ``BundleCatalog.get_variant`` / the
# variant's ``dashboard_template`` field and do NOT need an entry here.
_BUNDLE_TO_TEMPLATE: dict[str, str] = {
    "hr_management": "hr_management",
    "hr_hub": "hr_management",
    "project_mgmt": "project_management",
    "ticketing": "ticketing",
    "finance": "finance",
    "marketing": "marketing",
    "sales": "sales",
    "healthcare": "healthcare_hospital",
    "legal_services": "legal_litigation_firm",
    "construction_real_estate": "construction_general_contractor",
    "education": "education_k12",
    "all_microservices": "all_microservices_enterprise_saas",
    "generic": "generic_small_business",
}

_DEFAULT_TEMPLATES_DIR = Path(__file__).parents[4] / "dashboard_templates"


class DashboardTemplateRegistry:
    """Resolves and returns deep-copied dashboard template dicts.

    The registry preloads every ``.json`` file under
    ``dashboard_templates/``. Selection is driven by
    ``BundleCatalog.get_variant(bundle_key, variant_key)`` when a catalog is
    provided, and falls back to ``_BUNDLE_TO_TEMPLATE`` for bundles that
    declare no variants.
    """

    def __init__(
        self,
        templates_dir: Path = _DEFAULT_TEMPLATES_DIR,
        catalog: BundleCatalog | None = None,
    ) -> None:
        self._dir = templates_dir
        self._catalog = catalog
        self._cache: dict[str, dict] = {}
        self._load_all()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(
        self,
        bundle_key: str,
        variant_key: str | None = None,
    ) -> dict | None:
        """Return a deep copy of the template for ``(bundle_key, variant_key)``.

        Falls back to the bundle's default variant when ``variant_key`` is
        omitted or does not match. Returns ``None`` when the bundle has no
        variants and no legacy ``_BUNDLE_TO_TEMPLATE`` entry.
        """
        filename = self._resolve_filename(bundle_key, variant_key)
        if filename is None:
            return None
        template = self._cache.get(filename)
        if template is None:
            return None
        logger.info(
            "dashboard_template_registry: bundle=%s variant=%s → %s",
            bundle_key,
            variant_key,
            filename,
        )
        return copy.deepcopy(template)

    def supported_bundles(self) -> list[str]:
        """Return bundle keys that can resolve a template."""
        if self._catalog is None:
            return list(_BUNDLE_TO_TEMPLATE.keys())
        keys = set(_BUNDLE_TO_TEMPLATE.keys())
        for bundle in self._catalog.list_all():
            if bundle.variants:
                keys.add(bundle.bundle_key)
        return sorted(keys)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _resolve_filename(self, bundle_key: str, variant_key: str | None) -> str | None:
        if self._catalog is not None:
            variants = self._catalog.get_variants(bundle_key)
            if variants:
                resolved = None
                if variant_key is not None:
                    resolved = self._catalog.get_variant(bundle_key, variant_key)
                if resolved is None:
                    resolved = self._catalog.get_default_variant(bundle_key)
                if resolved is not None and resolved.dashboard_template:
                    return resolved.dashboard_template
        return _BUNDLE_TO_TEMPLATE.get(bundle_key)

    def _load_all(self) -> None:
        """Load every ``.json`` template found in the templates directory."""
        if not self._dir.is_dir():
            logger.warning(
                "DashboardTemplateRegistry: templates_dir not found: %s",
                self._dir,
            )
            return
        for path in sorted(self._dir.glob("*.json")):
            try:
                with path.open(encoding="utf-8") as f:
                    self._cache[path.stem] = json.load(f)
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning(
                    "Failed to load dashboard template %s: %s", path.name, exc
                )
                continue
            logger.info("Loaded dashboard template: %s", path.name)
