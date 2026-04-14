"""Pipeline node: resolves feature flags from user context and bundle catalog."""

from __future__ import annotations

from core.logging import get_logger

from ..state import PreviewGeneratorState

logger = get_logger(__name__)


def resolve_bundles_to_flags(state: PreviewGeneratorState) -> dict:
    """Resolve bundle_key → feature flags, permission_services, landing_pages.

    All 69 feature flags are enabled for every bundle — module activation is
    no longer bundle-specific. Bundle identity still drives permission_services,
    landing_pages, config, and dummy data stores.

    Unknown bundle_key is handled gracefully (empty permission_services /
    landing_pages; data_tier will fall through to Tier 3 fallback).

    Returns updates for:
      resolved_bundle_ids, feature_flags, permission_services, landing_pages
    """
    if state.catalog is None:
        logger.error("session=%s — BundleCatalog missing in state", state.session_id)
        return {
            "resolved_bundle_ids": [],
            "feature_flags": {},
            "permission_services": [],
            "landing_pages": [],
        }

    bundle_key = state.bundle_key

    # All flags are always enabled regardless of bundle.
    feature_flags: dict[str, bool] = {
        e["name"]: True for e in state.catalog.get_feature_flags()
    }

    bundle = state.catalog.get(bundle_key)

    if bundle is None:
        logger.info(
            "session=%s — bundle_key=%r not in catalog, no permission_services/landing_pages",
            state.session_id,
            bundle_key,
        )
        return {
            "resolved_bundle_ids": [],
            "feature_flags": feature_flags,
            "permission_services": [],
            "landing_pages": [],
        }

    # Collect permission_services and landing_pages from primary bundle + addons.
    bundle_ids = [bundle_key]
    for addon_key in bundle.compatible_addons:
        if state.catalog.has_bundle(addon_key):
            bundle_ids.append(addon_key)

    permission_services: list[str] = []
    landing_pages: list[dict] = []

    for bid in bundle_ids:
        b_def = state.catalog.get(bid)
        if b_def is None:
            continue
        for svc in b_def.permission_services:
            if svc not in permission_services:
                permission_services.append(svc)
        for lp in b_def.landing_pages:
            if lp not in landing_pages:
                landing_pages.append(lp)

    logger.info(
        "session=%s — bundle_key=%r all flags enabled, permission_services=%s",
        state.session_id,
        bundle_key,
        permission_services,
    )

    return {
        "resolved_bundle_ids": bundle_ids,
        "feature_flags": feature_flags,
        "permission_services": permission_services,
        "landing_pages": landing_pages,
    }
