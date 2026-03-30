"""Pipeline node: selects the data-generation tier for the current bundle."""

from __future__ import annotations

from core.logging import get_logger

from ..bundles.registry import BUNDLE_REGISTRY
from ..state import PreviewGeneratorState

logger = get_logger(__name__)


def select_data_tier(state: PreviewGeneratorState) -> dict:
    """Select the data generation tier based on bundle resolution.

    Tier 1 — bundle_key is in BUNDLE_REGISTRY and flags were resolved.
              Uses deterministic, programmatic sample data from name/value pools.
              Personalised from UserContext (work_type, people, teams).

    Tier 2 — (Phase 2) LLM-generated data for niche industries or
              unusual bundle combinations not covered by static pools.
              Currently falls through to Tier 3.

    Tier 3 — Fallback. bundle_key is unknown or resolution returned nothing.
              Uses generic placeholder data with no personalization.

    Returns: {"data_tier": "tier_1" | "tier_3"}
    """
    # resolved_bundle_ids[0] is the registry key (already translated from catalog key).
    # Checking against BUNDLE_REGISTRY must use the registry key, not state.bundle_key.
    flags_resolved = bool(state.resolved_bundle_ids)
    registry_key = state.resolved_bundle_ids[0] if flags_resolved else state.bundle_key
    is_known = registry_key in BUNDLE_REGISTRY

    if is_known and flags_resolved:
        tier = "tier_1"
    else:
        # TODO: Phase 2 — implement Tier 2 LLM-generated data for niche industries.
        # Route here when bundle is unknown but not entirely generic
        # (e.g. niche industry detected).
        tier = "tier_3"

    logger.info(
        "session=%s — bundle=%r (registry=%r) known=%s flags_resolved=%s → tier=%s",
        state.session_id,
        state.bundle_key,
        registry_key,
        is_known,
        flags_resolved,
        tier,
    )
    return {"data_tier": tier}
