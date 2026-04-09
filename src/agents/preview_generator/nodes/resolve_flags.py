"""Pipeline node: resolves feature flags from user context and bundle catalog."""

from __future__ import annotations

from core.logging import get_logger

from ..state import PreviewGeneratorState

logger = get_logger(__name__)


def resolve_bundles_to_flags(state: PreviewGeneratorState) -> dict:
    """Resolve bundle_key → feature flags, permission_services, landing_pages.

    Uses the canonical BundleCatalog from state to resolve definitions.
    Includes the primary bundle plus all of its compatible_addons.
    Unknown bundle_key is handled gracefully (empty sets; data_tier will
    fall through to Tier 3 fallback).

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
    bundle = state.catalog.get(bundle_key)

    if bundle is None:
        logger.warning(
            "session=%s — bundle_key=%r not in catalog, resolved nothing",
            state.session_id,
            bundle_key,
        )
        return {
            "resolved_bundle_ids": [],
            "feature_flags": {},
            "permission_services": [],
            "landing_pages": [],
        }

    # Collect primary + addons
    bundle_ids = [bundle_key]
    for addon_key in bundle.compatible_addons:
        if state.catalog.has_bundle(addon_key):
            bundle_ids.append(addon_key)

    # Accumulate across all resolved bundles
    flag_names_to_enable: set[str] = set()
    permission_services: list[str] = []
    landing_pages: list[dict] = []

    for bid in bundle_ids:
        b_def = state.catalog.get(bid)
        if b_def is None:
            continue
        flag_names_to_enable.update(b_def.flags)
        for svc in b_def.permission_services:
            if svc not in permission_services:
                permission_services.append(svc)
        for lp in b_def.landing_pages:
            if lp not in landing_pages:
                landing_pages.append(lp)

    # Apply to a fresh snapshot of all known flags
    snapshot = state.catalog.get_feature_flags()
    for entry in snapshot:
        if entry["name"] in flag_names_to_enable:
            entry["isEnabled"] = True

    feature_flags: dict[str, bool] = {e["name"]: e["isEnabled"] for e in snapshot}

    logger.info(
        "session=%s — resolved bundle_ids=%s enabled_flags=%d permission_services=%s",
        state.session_id,
        bundle_ids,
        sum(1 for v in feature_flags.values() if v),
        permission_services,
    )

    return {
        "resolved_bundle_ids": bundle_ids,
        "feature_flags": feature_flags,
        "permission_services": permission_services,
        "landing_pages": landing_pages,
    }
