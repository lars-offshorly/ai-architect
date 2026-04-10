"""Router: static mock endpoints for frontend integration.

Serves deterministic, pre-baked responses without running the AI pipeline,
LangGraph, or hitting the database. Business logic lives in MockPayloadBuilder;
this router is a thin HTTP adapter.

Guarded by the ENABLE_MOCK_ENDPOINTS setting — disabled in production.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from agents.app_generator.mock_builder import KNOWN_RENDER_KEYS, MockPayloadBuilder
from api.deps import get_mock_payload_builder
from core.exceptions import TemplateLoadError
from core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/mock", tags=["mock"])


# ---------------------------------------------------------------------------
# Shared guard
# ---------------------------------------------------------------------------


def _get_builder_or_404(
    bundle_key: str,
    builder: MockPayloadBuilder,
) -> MockPayloadBuilder:
    """Raise 404 for unknown render keys before hitting the builder."""
    if bundle_key not in KNOWN_RENDER_KEYS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown bundle key '{bundle_key}'. Valid keys: {sorted(KNOWN_RENDER_KEYS)}",
        )
    return builder


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/{bundle_key}")
def get_mock_payload(
    bundle_key: str,
    builder: Annotated[MockPayloadBuilder, Depends(get_mock_payload_builder)],
) -> dict[str, Any]:
    """Return a full static mock payload for a given bundle render key.

    Combines:
      - generation_json: verbatim app.json from the bundle template
      - dummy_data_json: verbatim dummy_data.json from the bundle template
      - feature_flags: flag snapshot with bundle-specific flags enabled
      - service_mocks: all sections from docs/api-mocks.json (chat, hrhub, etc.)
    """
    _get_builder_or_404(bundle_key, builder)

    try:
        payload = builder.build(bundle_key)
    except TemplateLoadError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Template load failed: {exc}",
        ) from exc

    logger.info("Mock payload served: bundle_key=%s", bundle_key)

    return {
        "bundle_key": payload.bundle_key,
        "generation_json": payload.generation_json,
        "dummy_data_json": payload.dummy_data_json,
        "feature_flags": payload.feature_flags,
        "service_mocks": payload.service_mocks,
    }


@router.get("/{bundle_key}/stores")
def get_mock_stores(
    bundle_key: str,
    builder: Annotated[MockPayloadBuilder, Depends(get_mock_payload_builder)],
) -> dict[str, Any]:
    """Return only the dummy_data_json (store seed data) for a bundle."""
    _get_builder_or_404(bundle_key, builder)

    try:
        dummy_data_json = builder.build_stores(bundle_key)
    except TemplateLoadError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Template load failed: {exc}",
        ) from exc

    logger.info("Mock stores served: bundle_key=%s", bundle_key)

    return {"bundle_key": bundle_key, "dummy_data_json": dummy_data_json}


@router.get("/{bundle_key}/flags")
def get_mock_flags(
    bundle_key: str,
    builder: Annotated[MockPayloadBuilder, Depends(get_mock_payload_builder)],
) -> dict[str, Any]:
    """Return the feature flag snapshot with bundle-specific flags enabled."""
    _get_builder_or_404(bundle_key, builder)

    flags, permission_services, landing_pages = builder.build_flags(bundle_key)

    logger.info("Mock flags served: bundle_key=%s", bundle_key)

    return {
        "bundle_key": bundle_key,
        "feature_flags": flags,
        "permission_services": permission_services,
        "landing_pages": landing_pages,
    }
