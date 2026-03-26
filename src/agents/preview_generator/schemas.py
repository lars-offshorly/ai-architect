"""Pydantic schemas for preview generator inputs, intermediate state, and output."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# KPI metrics
# ---------------------------------------------------------------------------


class KpiMetric(BaseModel):
    """A single KPI metric definition included in the preview output."""

    key: str
    label: str
    type: Literal["percentage", "count", "duration", "status", "ratio"]
    source_service: str
    sample_value: float | int | str


# ---------------------------------------------------------------------------
# Preview output payloads
# ---------------------------------------------------------------------------


class GenerationConfig(BaseModel):
    """Permission and navigation config embedded in the generation JSON."""

    permission_services: list[str]
    landing_pages: list[dict]


class GenerationJson(BaseModel):
    """Knit workspace configuration payload (feature flags, modules, config)."""

    schema_version: str
    bundle_key: str
    feature_flags: list[dict]  # shape: {id, name, description, isEnabled, module}
    modules: list[str]
    config: GenerationConfig


class DummyDataJson(BaseModel):
    """Sample data stores payload used to seed the preview workspace."""

    bundle_key: str
    session_id: str
    company_name: str | None = None
    stores: dict  # keys vary per bundle — stays untyped


class PreviewOutput(BaseModel):
    """Combined output of the preview pipeline: workspace config + sample data."""

    generation_json: GenerationJson
    dummy_data_json: DummyDataJson


class PersonDetail(BaseModel):
    """A person mentioned in the conversation — employee, team member, or the user
    themselves."""

    name: str | None = None
    role: str | None = None  # e.g. "Attorney", "Tech Lead"
    department: str | None = None
    is_user: bool = False  # True if this person is the one chatting


class TeamDetail(BaseModel):
    """A team or department mentioned in the conversation."""

    name: str
    size: int | None = None
    function: str | None = None  # e.g. "Engineering", "Litigation"


class WorkItemDetail(BaseModel):
    """A type of work item described in the conversation."""

    name: str | None = None
    work_type: str  # "sprint" | "litigation" | "waterfall" | "support_request"
    has_deadlines: bool = False
    methodology: str | None = None  # "agile" | "waterfall" | "kanban" | "hybrid"


class UserContext(BaseModel):
    """Extracted business context from conversation history.

    Produced by extract_user_context and consumed by generate_sample_data
    and build_kpi_metrics. Never serialized in an API request or response —
    internal pipeline state only.

    Why not ExtractedInfo (Dev A's model):
      ExtractedInfo carries flat lists (role_names: list[str]).
      generate_sample_data needs structured objects — work_items[].work_type
      to pick project naming strategy, and role+department paired per person.
    """

    company_name: str | None = None
    company_size: str | None = None  # "small" | "mid-sized" | "enterprise"
    industry_detail: str | None = None  # more specific than classification.industry
    people: list[PersonDetail] = Field(default_factory=list)
    teams: list[TeamDetail] = Field(default_factory=list)
    work_items: list[WorkItemDetail] = Field(default_factory=list)
    has_remote_teams: bool | None = None
    has_clients: bool | None = None  # external client work vs internal
    work_methodology: str | None = None  # "agile" | "waterfall" | "hybrid"
    primary_concern: str | None = None  # user's main pain point
    key_phrases: list[str] = Field(
        default_factory=list
    )  # signal phrases for KPI matching
