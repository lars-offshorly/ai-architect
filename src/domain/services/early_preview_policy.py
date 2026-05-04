from __future__ import annotations

from domain.models.session import Session

CONFIDENCE_THRESHOLD = 0.6
FALLBACK_BUNDLE_KEY = "all_microservices"


def resolve_early_bundle_key(session: Session) -> str:
    """Return the best available bundle key for early (unconfirmed) preview."""
    if session.selected_bundle_key:
        return session.selected_bundle_key
    if session.preselected_bundle_key:
        return session.preselected_bundle_key
    if (
        session.latest_recommendation is not None
        and session.latest_recommendation.primary_bundle is not None
    ):
        return session.latest_recommendation.primary_bundle.bundle_key
    if session.latest_classification:
        top_confidence = session.latest_classification.top_confidence
        top_key = (
            session.latest_classification.selected_bundle.bundle_key
            if session.latest_classification.selected_bundle is not None
            else None
        )
        if top_key and top_confidence >= CONFIDENCE_THRESHOLD:
            return top_key
    return FALLBACK_BUNDLE_KEY
