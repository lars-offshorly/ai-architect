from __future__ import annotations

from pydantic import BaseModel, Field


class StartSessionRequest(BaseModel):
    message: str = Field(min_length=1)
    user_id: str | None = None
    preselected_bundle_key: str | None = Field(
        default=None,
        description=(
            "Optional. Skip AI classification and use this bundle key directly. "
            "Must match a key in the bundle registry. "
            "Returns HTTP 400 for unknown keys."
        ),
    )
    preselected_intent: str | None = Field(
        default=None,
        description=(
            "Optional. A known intent string from the bundle registry "
            "(e.g. 'manage employees') "
            "to guide classification and boost matching bundles. "
            "Returns HTTP 400 for unrecognised intents. "
            "Persisted across all turns of the session."
        ),
    )


class ReplyRequest(BaseModel):
    message: str = Field(min_length=1)
    force_preview: bool = Field(
        default=False,
        description=(
            "Optional. If true, immediately returns a preview with the "
            "best available bundle "
            "without requiring missing-field completion or bundle confirmation. "
            "The response will include a warning and preview_type='early'."
        ),
    )


class ConfirmBundleRequest(BaseModel):
    confirmed: bool
