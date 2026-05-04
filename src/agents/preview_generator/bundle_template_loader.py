"""Loads and returns bundle app-0*.json variants from ``src/templates/bundles/``.

Each bundle directory may contain up to 3 variant files (``app-01.json``,
``app-02.json``, ``app-03.json``). Variants are keyed by the filename stem
(e.g. ``app-01``); that key is what the interpreter's ``VariantSelector``
emits on ``BundleSuggestion.variant_key``.

Selection logic
---------------
1. If ``variant_key`` is provided and matches a loaded variant, return it.
2. Otherwise, return the first variant loaded (``app-01`` by filename order),
   which corresponds to the bundle's default flavour.

The caller (PreviewFlow) overlays the template's ``stores`` dict onto the
pipeline-generated ``dummy_data_json``, replacing operational data (tickets,
projects, tasks …) with realistic, domain-specific fixtures while keeping the
pipeline-generated KPIs and letting dashboard enrichment fill
``dashboard_widgets``.
"""

from __future__ import annotations

import json
from pathlib import Path

from core.logging import get_logger

logger = get_logger(__name__)

_DEFAULT_BUNDLES_DIR = Path(__file__).parents[2] / "templates" / "bundles"

# Store keys that must NOT be overlaid from the static template — these are
# owned by the pipeline (kpis) or the dashboard enrichment service
# (dashboard_widgets / dashboard_generation_output).
_PIPELINE_OWNED_STORE_KEYS: frozenset[str] = frozenset(
    {"kpis", "dashboard_widgets", "dashboard_generation_output"}
)


class BundleTemplateLoader:
    """Loads all ``app-0*.json`` variants per bundle and resolves by variant key.

    All variants are loaded once at construction time and cached.  ``load()``
    is a pure in-memory look-up after that.
    """

    def __init__(self, bundles_dir: Path = _DEFAULT_BUNDLES_DIR) -> None:
        self._dir = bundles_dir
        # bundle_key → [variant_dicts in filename order]
        self._variants: dict[str, list[dict]] = {}
        # (bundle_key, variant_key) → variant_dict
        self._by_variant: dict[tuple[str, str], dict] = {}
        self._load_all()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(
        self,
        bundle_key: str,
        variant_key: str | None = None,
    ) -> dict | None:
        """Return the variant dict for ``(bundle_key, variant_key)`` or None.

        When ``variant_key`` is ``None`` or not found for this bundle, the
        first variant in filename order (``app-01``) is returned.  The caller
        gets a direct reference to the cached object — callers that need to
        mutate it should ``copy.deepcopy`` first.
        """
        candidates = self._variants.get(bundle_key)
        if not candidates:
            return None

        if variant_key is not None:
            chosen = self._by_variant.get((bundle_key, variant_key))
            if chosen is not None:
                logger.info(
                    "bundle_template_loader: bundle=%s variant=%s → %s",
                    bundle_key,
                    variant_key,
                    chosen.get("_source_file", "?"),
                )
                return chosen
            logger.info(
                "bundle_template_loader: bundle=%s variant=%s not found; "
                "falling back to default",
                bundle_key,
                variant_key,
            )

        chosen = candidates[0]
        logger.info(
            "bundle_template_loader: bundle=%s → %s (default variant)",
            bundle_key,
            chosen.get("_source_file", "?"),
        )
        return chosen

    def supported_bundles(self) -> list[str]:
        """Return bundle keys that have at least one variant loaded."""
        return list(self._variants.keys())

    def variant_keys(self, bundle_key: str) -> list[str]:
        """Return the variant keys loaded for ``bundle_key`` in filename order."""
        return [
            variant["_variant_key"]
            for variant in self._variants.get(bundle_key, [])
            if "_variant_key" in variant
        ]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load_all(self) -> None:
        if not self._dir.exists():
            logger.warning("BundleTemplateLoader: bundles_dir not found: %s", self._dir)
            return

        for variant_path in sorted(self._dir.glob("*/app-0*.json")):
            try:
                with variant_path.open(encoding="utf-8") as f:
                    data: dict = json.load(f)
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning(
                    "BundleTemplateLoader: failed to load %s: %s",
                    variant_path,
                    exc,
                )
                continue

            bundle_key = data.get("bundle_key")
            if not bundle_key:
                logger.warning(
                    "BundleTemplateLoader: %s has no bundle_key, skipping",
                    variant_path.name,
                )
                continue

            variant_key = variant_path.stem
            data["_source_file"] = f"{variant_path.parent.name}/{variant_path.name}"
            data["_variant_key"] = variant_key
            self._variants.setdefault(bundle_key, []).append(data)
            self._by_variant[(bundle_key, variant_key)] = data
            logger.info(
                "BundleTemplateLoader: loaded %s → bundle_key=%s variant_key=%s",
                variant_path.name,
                bundle_key,
                variant_key,
            )
