"""Pipeline node: resolves feature flags from user context and bundle catalog."""

from __future__ import annotations

from core.logging import get_logger

from ..bundles.registry import BUNDLE_REGISTRY, get_flag_snapshot
from ..state import PreviewGeneratorState

logger = get_logger(__name__)


def _collect_bundle_ids(primary_key: str) -> list[str]:
    """Return primary bundle key plus any known compatible addons."""
    ids = [primary_key]
    for addon_key in BUNDLE_REGISTRY.get(primary_key, {}).get("compatible_addons", []):
        if addon_key in BUNDLE_REGISTRY:
            ids.append(addon_key)
    return ids


def _accumulate(bundle_ids: list[str]) -> tuple[set[str], list[str], list[dict]]:
    """Merge flags, permission_services, and landing_pages across all bundle ids."""
    flags: set[str] = set()
    services: list[str] = []
    pages: list[dict] = []
    for bid in bundle_ids:
        bundle = BUNDLE_REGISTRY.get(bid, {})
        flags.update(bundle.get("flags", []))
        for svc in bundle.get("permission_services", []):
            if svc not in services:
                services.append(svc)
        for lp in bundle.get("landing_pages", []):
            if lp not in pages:
                pages.append(lp)
    return flags, services, pages


def resolve_bundles_to_flags(state: PreviewGeneratorState) -> dict:
    """Resolve bundle_key → feature flags, permission_services, landing_pages.

    Translates catalog bundle keys to registry keys before lookup.
    Includes the primary bundle plus all of its compatible_addons.
    Unknown bundle_key is handled gracefully (empty sets; data_tier will
    fall through to Tier 3 fallback).

    Returns updates for:
      resolved_bundle_ids, feature_flags, permission_services, landing_pages
    """
    bundle_key = state.bundle_key

    if bundle_key not in BUNDLE_REGISTRY:
        logger.warning(
            "session=%s — bundle_key=%r not in registry, resolved nothing",
            state.session_id,
            bundle_key,
        )
        return {
            "resolved_bundle_ids": [],
            "feature_flags": {},
            "permission_services": [],
            "landing_pages": [],
        }

    bundle_ids = _collect_bundle_ids(bundle_key)
    flag_names_to_enable, permission_services, landing_pages = _accumulate(bundle_ids)

    snapshot = get_flag_snapshot()
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
