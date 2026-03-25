from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from .schemas import KpiMetric, PreviewOutput, UserContext


class PreviewGeneratorState(BaseModel):
    """Working memory for the 7-node LangGraph preview pipeline.

    Set at graph entry:
      session_id, bundle_key, conversation_history

    Populated by nodes in execution order:
      user_context        ← extract_user_context
      resolved_bundle_ids,
      feature_flags,
      permission_services,
      landing_pages       ← resolve_bundles_to_flags
      data_tier           ← select_data_tier
      sample_*            ← generate_sample_data
      kpi_metrics         ← build_kpi_metrics
      schema_valid,
      validation_errors,
      retry_count         ← validate_schema
      output              ← emit_preview
    """

    # --- Inputs (set at graph entry, never mutated) ---
    session_id: str
    bundle_key: str
    conversation_history: list[dict] = Field(default_factory=list)
    # conversation_history items: {"role": "user"|"assistant", "content": str}

    # --- extract_user_context ---
    user_context: Optional[UserContext] = None

    # --- resolve_bundles_to_flags ---
    resolved_bundle_ids: list[str] = Field(default_factory=list)
    # feature_flags: name → isEnabled (working copy, not the final serialized form)
    feature_flags: dict[str, bool] = Field(default_factory=dict)
    permission_services: list[str] = Field(default_factory=list)
    landing_pages: list[dict] = Field(default_factory=list)

    # --- select_data_tier ---
    data_tier: Optional[Literal["tier_1", "tier_2", "tier_3"]] = None

    # --- generate_sample_data ---
    sample_employees: list[dict] = Field(default_factory=list)
    sample_projects: list[dict] = Field(default_factory=list)
    sample_tickets: list[dict] = Field(default_factory=list)
    sample_weaves: list[dict] = Field(default_factory=list)

    # --- build_kpi_metrics ---
    kpi_metrics: list[KpiMetric] = Field(default_factory=list)

    # --- validate_schema ---
    schema_valid: bool = False
    validation_errors: list[str] = Field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 2

    # --- emit_preview ---
    output: Optional[PreviewOutput] = None
