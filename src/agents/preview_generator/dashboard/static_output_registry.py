"""Static pre-generated dashboard widget outputs.

Instead of calling the live Dashboard Gen service, the Preview Generator
loads these pre-computed widget layouts directly.  Each file under
``dashboard_output_templates/`` contains the final internal widget format used
by preview payloads.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from catalog.bundle_catalog import BundleCatalog
from core.logging import get_logger

logger = get_logger(__name__)

# Legacy fallback mapping for bundles without catalog variants.
_BUNDLE_TO_OUTPUT: dict[str, str] = {
    "hr_management": "hr_management",
    "hr_hub": "hr_management",
    "project_mgmt": "project_management",
    "ticketing": "ticketing",
    "finance": "finance",
    "marketing": "marketing",
    "sales": "sales",
    "healthcare": "healthcare_hospital",
    "legal_services": "legal_litigation_firm",
    "construction": "construction_general_contractor",
    "real_estate": "real_estate_property_mgmt",
    "education": "education_k12",
    "all_microservices": "all_microservices_enterprise_saas",
    "generic": "generic_small_business",
}

_DEFAULT_OUTPUT_DIR = Path(__file__).parents[4] / "dashboard_output_templates"


class StaticDashboardOutputRegistry:
    """Returns pre-generated widget lists.

    Resolution order:
    1. BundleCatalog variant → ``dashboard_template`` field (same stem used for outputs)
    2. ``_BUNDLE_TO_OUTPUT`` legacy fallback

    Deep copies are returned so callers can mutate safely.
    """

    def __init__(
        self,
        output_dir: Path = _DEFAULT_OUTPUT_DIR,
        catalog: BundleCatalog | None = None,
    ) -> None:
        self._dir = output_dir
        self._catalog = catalog
        self._cache: dict[str, list[dict]] = {}
        self._load_all()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_widgets(
        self,
        bundle_key: str,
        variant_key: str | None = None,
    ) -> list[dict] | None:
        """Return a deep copy of the pre-generated widget list, or None if unknown."""
        stem = self._resolve_stem(bundle_key, variant_key)
        if stem is None:
            return None
        widgets = self._cache.get(stem)
        if widgets is None:
            return None
        logger.info(
            "static_output_registry: bundle=%s variant=%s → %s (%d widgets)",
            bundle_key,
            variant_key,
            stem,
            len(widgets),
        )
        return copy.deepcopy(widgets)

    def supported_bundles(self) -> list[str]:
        """Bundle keys that have a pre-generated output file loaded."""
        supported = []
        for bundle_key, stem in _BUNDLE_TO_OUTPUT.items():
            if stem in self._cache:
                supported.append(bundle_key)
        if self._catalog is not None:
            for bundle in self._catalog.list_all():
                if not bundle.variants:
                    continue
                for variant in bundle.variants:
                    if (
                        variant.dashboard_template
                        and variant.dashboard_template in self._cache
                    ):
                        if bundle.bundle_key not in supported:
                            supported.append(bundle.bundle_key)
                        break
        return sorted(supported)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _resolve_stem(self, bundle_key: str, variant_key: str | None) -> str | None:
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
        return _BUNDLE_TO_OUTPUT.get(bundle_key)

    def _load_all(self) -> None:
        if not self._dir.is_dir():
            logger.warning(
                "StaticDashboardOutputRegistry: output_dir not found: %s", self._dir
            )
            return
        for path in sorted(self._dir.glob("*.json")):
            try:
                with path.open(encoding="utf-8") as f:
                    data = json.load(f)
                widgets = data.get("widgets")
                if not isinstance(widgets, list) or not widgets:
                    raise ValueError("missing or empty widgets list")
                if not all(isinstance(widget, dict) for widget in widgets):
                    raise ValueError("widgets must contain only objects")
                self._cache[path.stem] = widgets
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning(
                    "Failed to load static dashboard output %s: %s", path.name, exc
                )
            except ValueError as exc:
                logger.warning("Invalid static dashboard output %s: %s", path.name, exc)
            else:
                logger.info("Loaded static dashboard output: %s", path.name)
