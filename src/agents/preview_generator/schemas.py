"""Pydantic schemas for preview generator inputs, intermediate state, and output."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

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


class GenerationJson(BaseModel):
    """Knit workspace configuration payload (feature flags, modules, config)."""

    schema_version: str
    bundle_key: str
    feature_flags: list[dict]  # shape: {id, name, description, isEnabled, module}
    modules: list[str]
    config: dict[str, object]


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


# ---------------------------------------------------------------------------
# Edit sub-graph
# ---------------------------------------------------------------------------


class EditActionType(str, Enum):
    ADD_MODULE = "add_module"
    REMOVE_MODULE = "remove_module"
    ADD_KPI = "add_kpi"
    REMOVE_KPI = "remove_kpi"
    ADD_DASHBOARD = "add_dashboard"
    REMOVE_DASHBOARD = "remove_dashboard"
    ADD_QUEUE = "add_queue"
    REMOVE_QUEUE = "remove_queue"
    ADD_DASHBOARD_BY_ID = "add_dashboard_by_id"
    REMOVE_DASHBOARD_BY_ID = "remove_dashboard_by_id"
    UNSUPPORTED = "unsupported"


class EditAction(BaseModel):
    action_type: EditActionType
    target: str | None = None
    raw_instruction: str = ""


# ---------------------------------------------------------------------------
# v2 Tenant Provisioning Manifest models
# ---------------------------------------------------------------------------


class TenantInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_name: str
    industry: str
    size_band: str
    primary_region: str
    locale: str
    timezone: str


class CatalogRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int = Field(..., gt=0)
    name: str


class EmployeeRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int = Field(..., gt=0)
    position: str
    team: str
    department: str
    job_title: str
    job_type: str
    job_level: str


class TicketQueuesSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queues: list[CatalogRef]


class ProjectsSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projects: list[CatalogRef]


class DashboardSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dashboards: list[CatalogRef]


class KpiSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kpis: list[CatalogRef]


class HrHubSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employees: list[EmployeeRecord]
    request_types: list[CatalogRef]


class TenantProvisioningManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["2.0"]
    session_id: str
    generated_at: str
    tenant: TenantInfo
    tickets: TicketQueuesSection
    projects: ProjectsSection
    dashboard: DashboardSection
    kpi: KpiSection
    hr_hub: HrHubSection


AppPayloadV2 = TenantProvisioningManifest
