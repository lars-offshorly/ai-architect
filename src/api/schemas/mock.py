"""Request schema for the static mock payload endpoint."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class MockPayloadRequestSchema(BaseModel):
    """Request body for POST /mock/{bundle_key}.

    All fields are optional — omitting dummy_data_json falls back to the
    bundle template file (dummy_data.json).

    Fields:
        session_id:      Injected into dummy_data_json.session_id when provided.
                         Ignored if dummy_data_json already contains session_id.
        display_name:    Human-readable workspace name surfaced in the response.
        dummy_data_json: Full store override in the same shape as dummy_data.json.
                         Accepted fields: bundle_key, session_id, company_name, stores.
                         When supplied the template file is not read at all.
    """

    session_id: str | None = None
    display_name: str | None = None
    dummy_data_json: dict[str, Any] | None = None
