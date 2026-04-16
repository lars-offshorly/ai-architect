"""Loads and selects bundle dummy-data templates from src/templates/bundles/.

Each bundle directory may contain up to 3 variant files (app-01.json,
app-02.json, app-03.json).  Each variant carries a ``keywords`` list used for
semantic matching against the intent classifier's ``primary_use_case`` field.

Selection logic
---------------
1. Collect all variants whose ``bundle_key`` matches the requested key.
2. If ``primary_use_case`` is given, score each variant by counting how many
   of its keywords appear (case-insensitive substring) in the string.
3. Return the highest-scoring variant; ties resolved by file order (app-01
   wins over app-02, etc.).  Falls back to the first variant when
   ``primary_use_case`` is absent or produces all-zero scores.

The caller (PreviewFlow) overlays the template's ``stores`` dict onto the
pipeline-generated ``dummy_data_json``, replacing operational data (tickets,
projects, tasks …) with realistic, domain-specific fixtures while keeping the
pipeline-generated KPIs and letting dashboard enrichment fill ``dashboard_widgets``.
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
    {"dashboard_widgets", "dashboard_generation_output"}
)


class BundleTemplateLoader:
    """Loads all app-0*.json variants per bundle and returns the best match.

    All variants are loaded once at construction time and cached.  ``load()``
    is a pure in-memory look-up after that.
    """

    def __init__(self, bundles_dir: Path = _DEFAULT_BUNDLES_DIR) -> None:
        self._dir = bundles_dir
        # bundle_key → list of parsed variant dicts, ordered by filename
        self._variants: dict[str, list[dict]] = {}
        self._load_all()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(
        self,
        bundle_key: str,
        primary_use_case: str | None = None,
    ) -> dict | None:
        """Return the best-matching variant for *bundle_key*, or None.

        The returned dict is a direct reference to the cached object — callers
        that need to mutate it should ``copy.deepcopy`` first.  PreviewFlow
        only reads ``stores`` values, so a shallow dict reference is fine.
        """
        candidates = self._variants.get(bundle_key)
        if not candidates:
            return None

        if len(candidates) == 1 or not primary_use_case:
            chosen = candidates[0]
            logger.info(
                "bundle_template_loader: bundle=%s → %s (first/only variant)",
                bundle_key,
                chosen.get("_source_file", "?"),
            )
            return chosen

        scored = [
            (self._score(c.get("keywords", []), primary_use_case), i, c)
            for i, c in enumerate(candidates)
        ]
        # sort descending by score, then ascending by index (app-01 wins ties)
        scored.sort(key=lambda x: (-x[0], x[1]))
        best_score, _, chosen = scored[0]

        logger.info(
            "bundle_template_loader: bundle=%s primary_use_case=%r → %s (score=%d)",
            bundle_key,
            primary_use_case,
            chosen.get("_source_file", "?"),
            best_score,
        )
        return chosen

    def supported_bundles(self) -> list[str]:
        """Return bundle keys that have at least one variant loaded."""
        return list(self._variants.keys())

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load_all(self) -> None:
        if not self._dir.exists():
            logger.warning(
                "BundleTemplateLoader: bundles_dir not found: %s", self._dir
            )
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

            # Stash source path (folder/filename) for debug logging (not part of schema)
            data["_source_file"] = f"{variant_path.parent.name}/{variant_path.name}"
            self._variants.setdefault(bundle_key, []).append(data)
            logger.info(
                "BundleTemplateLoader: loaded %s → bundle_key=%s",
                variant_path.name,
                bundle_key,
            )

    @staticmethod
    def _score(keywords: list, use_case: str) -> int:
        """Count how many keywords appear (case-insensitive) in *use_case*."""
        use_case_lower = use_case.lower()
        return sum(
            1
            for kw in keywords
            if isinstance(kw, str) and kw.lower() in use_case_lower
        )
