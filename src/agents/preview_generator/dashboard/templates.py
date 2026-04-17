"""Dashboard template registry.

Loads dashboard templates from the ``dashboard_templates/`` directory and
resolves the correct template for a given bundle key.

Templates are loaded once on first access and cached for the process lifetime.
Adding support for a new bundle requires dropping a new ``.json`` file into
``dashboard_templates/`` and adding a mapping entry to ``_BUNDLE_TO_TEMPLATE``
(primary/fallback) and, optionally, additional filenames to
``_BUNDLE_VARIANTS`` (flavour variants selected by keyword scoring).

Variant selection mirrors ``BundleTemplateLoader``: when a ``primary_use_case``
string is provided, each candidate's top-level ``keywords`` list is scored
(case-insensitive substring match) and the best-scoring file wins.  Ties and
zero-score cases fall back to the primary filename.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from core.logging import get_logger

logger = get_logger(__name__)

# Map from catalog/registry bundle key → primary template filename (without .json).
# Bundles not listed here receive None from get() and skip the dashboard call.
_BUNDLE_TO_TEMPLATE: dict[str, str] = {
    "hr_management": "hr_management",
    "hr_hub": "hr_management",  # render key alias
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

# Additional flavour variants per bundle.  Scored against ``primary_use_case``
# (see ``DashboardTemplateRegistry.get``).  The primary filename from
# ``_BUNDLE_TO_TEMPLATE`` is always a candidate and also acts as fallback.
_BUNDLE_VARIANTS: dict[str, list[str]] = {
    "hr_management": ["hr_management_recruiting", "hr_management_onboarding"],
    "hr_hub": ["hr_management_recruiting", "hr_management_onboarding"],
    "project_mgmt": [
        "project_management_client_delivery",
        "project_management_creative",
    ],
    "ticketing": ["ticketing_customer_support", "ticketing_facilities"],
    "finance": ["finance_enterprise", "finance_real_estate"],
    "marketing": ["marketing_content", "marketing_events"],
    "sales": ["sales_brokerage", "sales_wholesale"],
}

_DEFAULT_TEMPLATES_DIR = Path(__file__).parents[4] / "dashboard_templates"


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

    def get(
        self,
        bundle_key: str,
        primary_use_case: str | None = None,
    ) -> dict | None:
        """Return a deep copy of the best template for ``bundle_key``, or None.

        When ``primary_use_case`` is supplied and the bundle has flavour
        variants registered in ``_BUNDLE_VARIANTS``, the variant whose
        ``keywords`` field best matches the string wins.  Falls back to the
        primary filename on ties, zero-score matches, or when no variants are
        registered.
        """
        primary = _BUNDLE_TO_TEMPLATE.get(bundle_key)
        if primary is None:
            return None

        variants = _BUNDLE_VARIANTS.get(bundle_key, [])
        if not variants or not primary_use_case:
            template = self._cache.get(primary)
            return copy.deepcopy(template) if template is not None else None

        # Candidates: primary first (tiebreaker and fallback), then variants.
        candidates: list[str] = [primary, *variants]
        scored = [
            (self._score(self._cache.get(name, {}).get("keywords", []), primary_use_case), i, name)
            for i, name in enumerate(candidates)
            if name in self._cache
        ]
        if not scored:
            return None

        scored.sort(key=lambda x: (-x[0], x[1]))
        best_score, _, chosen = scored[0]

        # Zero score → fall back to primary so we never pick a flavour by accident.
        if best_score == 0:
            chosen = primary

        logger.info(
            "dashboard_template_registry: bundle=%s primary_use_case=%r → %s (score=%d)",
            bundle_key,
            primary_use_case,
            chosen,
            best_score,
        )
        template = self._cache.get(chosen)
        return copy.deepcopy(template) if template is not None else None

    @staticmethod
    def _score(keywords: list, use_case: str) -> int:
        """Count how many keywords appear (case-insensitive) in *use_case*."""
        use_case_lower = use_case.lower()
        return sum(
            1
            for kw in keywords
            if isinstance(kw, str) and kw.lower() in use_case_lower
        )

    def supported_bundles(self) -> list[str]:
        """Return the bundle keys that have a registered template."""
        return list(_BUNDLE_TO_TEMPLATE.keys())

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load_all(self) -> None:
        """Load every template referenced by the registry mappings at init."""
        filenames: set[str] = set(_BUNDLE_TO_TEMPLATE.values())
        for variant_list in _BUNDLE_VARIANTS.values():
            filenames.update(variant_list)
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
