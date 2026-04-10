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
from api.schemas.mock import MockPayloadRequestSchema
from core.exceptions import InvalidPayloadError, TemplateLoadError
from core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/mock", tags=["mock"])


# ---------------------------------------------------------------------------
# Shared guard
# ---------------------------------------------------------------------------


def _validate_bundle_key(bundle_key: str) -> None:
    """Raise 404 for unknown render keys."""
    if bundle_key not in KNOWN_RENDER_KEYS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown bundle key '{bundle_key}'. Valid keys: {sorted(KNOWN_RENDER_KEYS)}",
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/{bundle_key}")
def get_mock_payload(
    bundle_key: str,
    body: MockPayloadRequestSchema,
    builder: Annotated[MockPayloadBuilder, Depends(get_mock_payload_builder)],
) -> dict[str, Any]:
    """Return a full mock payload for a given bundle render key.

    Accepts an optional request body to supply custom dummy_data_json.
    When dummy_data_json is omitted the bundle template file is used instead.

    Request body (all fields optional):
      - session_id:      Injected into dummy_data_json if not already present.
      - display_name:    Human-readable workspace name surfaced in the response.
      - dummy_data_json: Full store data override. Accepted shape:
                           { bundle_key, session_id, company_name, stores: {...} }
                         When provided the template dummy_data.json is skipped.

    Response combines:
      - generation_json:  verbatim app.json from the bundle template
      - dummy_data_json:  caller-supplied override OR template fallback
      - feature_flags:    flag snapshot with bundle-specific flags enabled
      - service_mocks:    all sections from docs/api-mocks.json
    """
    _validate_bundle_key(bundle_key)

    try:
        payload = builder.build(
            bundle_key=bundle_key,
            dummy_data_override=body.dummy_data_json,
            session_id=body.session_id,
        )
    except InvalidPayloadError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except TemplateLoadError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Template load failed: {exc}",
        ) from exc

    logger.info(
        "Mock payload served: bundle_key=%s display_name=%s source=%s",
        bundle_key,
        body.display_name,
        "override" if body.dummy_data_json is not None else "template",
    )

    return {
        "bundle_key": payload.bundle_key,
        "display_name": body.display_name,
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
    """Return only the template dummy_data_json (store seed data) for a bundle."""
    _validate_bundle_key(bundle_key)

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
    _validate_bundle_key(bundle_key)

    flags, permission_services, landing_pages = builder.build_flags(bundle_key)

    logger.info("Mock flags served: bundle_key=%s", bundle_key)

    return {
        "bundle_key": bundle_key,
        "feature_flags": flags,
        "permission_services": permission_services,
        "landing_pages": landing_pages,
    }
