"""LangGraph state definition for the preview generator pipeline."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from catalog.bundle_catalog import BundleCatalog
from domain.models.extraction_result import ExtractionResult

from .schemas import KpiMetric, UserContext


class PreviewGeneratorState(BaseModel):
    """Working memory for the 7-node LangGraph preview pipeline.

    Set at graph entry:
      session_id, bundle_key, conversation_history,
      extraction_result, preselected_intent, catalog

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

    extraction_result is the primary driver for extract_user_context when
    present — it carries Dev A's accumulated structured output and avoids a
    redundant LLM call inside the preview pipeline.

    preselected_intent is set when the user chose a use-case before chatting
    (e.g. "onboarding", "policies"). Used as a workflow_hints supplement when
    classification_signals is empty.
    """

    # --- Inputs (set at graph entry, never mutated) ---
    session_id: str
    bundle_key: str
    conversation_history: list[dict] = Field(default_factory=list)
    # conversation_history items: {"role": "user"|"assistant", "content": str}

    # Canonical catalog resource used by resolve_flags and kpi nodes.
    catalog: BundleCatalog | None = None

    # Dev A's accumulated extraction — when present, extract_user_context maps
    # its fields directly to UserContext instead of re-running keyword scan or LLM.
    extraction_result: ExtractionResult | None = None

    # User-chosen intent before conversation started (Lars scenario #2).
    # Supplements workflow_hints when classification_signals is empty.
    preselected_intent: str | None = None

    # --- extract_user_context ---
    user_context: UserContext | None = None

    # --- resolve_bundles_to_flags ---
    resolved_bundle_ids: list[str] = Field(default_factory=list)
    # feature_flags: name → isEnabled (working copy, not the final serialized form)
    feature_flags: dict[str, bool] = Field(default_factory=dict)
    permission_services: list[str] = Field(default_factory=list)
    landing_pages: list[dict] = Field(default_factory=list)

    # --- select_data_tier ---
    data_tier: Literal["tier_1", "tier_2", "tier_3"] | None = None

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
    output: dict[str, object] | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)
