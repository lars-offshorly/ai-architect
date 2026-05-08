"""Pydantic schemas for preview generator inputs, intermediate state, and output."""

from __future__ import annotations

from collections.abc import Iterator
from enum import Enum
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


# ---------------------------------------------------------------------------
# Target contract schemas (ADR-003)
# Mirrors Murad's knit-builder OpenAPI spec for POST /organizations/me/generate/
# Pattern: { module: { entityTemplates: [{id, name?}] } }
# IDs are template IDs, matching the dashboards pattern (template IDs 57/54/64/62).
# Non-dashboard template IDs are pending Murad confirmation (Phase 9) — those
# modules remain null until IDs are known.
# ---------------------------------------------------------------------------


class WidgetTemplateGenerateSchema(BaseModel):
    """Widget template reference for dashboard generation."""

    id: int = Field(..., gt=0, description="Pre-created widget template ID.")
    name: str | None = Field(None, description="Rename only — omit to keep existing.")


class DashboardTemplateGenerateSchema(BaseModel):
    """Dashboard template reference plus its widget template references."""

    id: int = Field(..., gt=0, description="Pre-created dashboard template ID.")
    name: str | None = Field(None, description="Rename only — omit to keep existing.")
    widgetTemplates: list[WidgetTemplateGenerateSchema] = Field(default_factory=list)


class DashboardModuleGenerateSchema(BaseModel):
    """Dashboard module payload for the knit-builder generation endpoint."""

    dashboardTemplates: list[DashboardTemplateGenerateSchema]


class TicketTemplateGenerateSchema(BaseModel):
    """Ticket template reference for future ticket module generation."""

    id: int = Field(..., gt=0)
    name: str | None = None


class TicketModuleGenerateSchema(BaseModel):
    """Ticket module payload for the knit-builder generation endpoint."""

    ticketTemplates: list[TicketTemplateGenerateSchema]


class ProjectTemplateGenerateSchema(BaseModel):
    """Project template reference for future project module generation."""

    id: int = Field(..., gt=0)
    name: str | None = None


class ProjectModuleGenerateSchema(BaseModel):
    """Project module payload for the knit-builder generation endpoint."""

    projectTemplates: list[ProjectTemplateGenerateSchema]


class HrHubTemplateGenerateSchema(BaseModel):
    """HR Hub template reference for future HR module generation."""

    id: int = Field(..., gt=0)
    name: str | None = None


class HrHubModuleGenerateSchema(BaseModel):
    """HR Hub module payload for the knit-builder generation endpoint."""

    hrHubTemplates: list[HrHubTemplateGenerateSchema]


class KpiTemplateGenerateSchema(BaseModel):
    """KPI template reference for future KPI module generation."""

    id: int = Field(..., gt=0)
    name: str | None = None


class KpiSchemaGenerateSchema(BaseModel):
    """KPI module payload for the knit-builder generation endpoint."""

    kpiTemplates: list[KpiTemplateGenerateSchema]


class GenerationSchema(BaseModel):
    """Request body schema for POST /organizations/me/generate/ (Murad's endpoint).

    Only `dashboards` is populated today — other modules remain null until
    template IDs are confirmed with Murad/BE (Phase 9).
    """

    dashboards: DashboardModuleGenerateSchema | None = None
    projects: ProjectModuleGenerateSchema | None = None
    tickets: TicketModuleGenerateSchema | None = None
    hrHub: HrHubModuleGenerateSchema | None = None
    kpi: KpiSchemaGenerateSchema | None = None


class SampleDataServices(BaseModel):
    """Defines the structure for service-oriented sample data records.

    Each field corresponds to a backend service and holds the sample data
    required for seeding or importing into that service.
    """

    tickets: dict[str, object] = Field(default_factory=lambda: {"queues": []})
    projects: dict[str, object] = Field(default_factory=lambda: {"projects": []})
    hrHub: dict[str, object] = Field(
        default_factory=lambda: {"teams": [], "employees": []}
    )
    weaves: dict[str, object] = Field(
        default_factory=lambda: {"folders": [], "worksheets": []}
    )
    calendar: dict[str, object] = Field(default_factory=lambda: {"calendars": []})
    kpi: dict[str, object] = Field(default_factory=lambda: {"kpis": []})


class SampleData(BaseModel):
    """Represents the complete payload for seeding a workspace with sample data.

    This model is structured around backend services rather than frontend state,
    containing all necessary information for data import flows.
    """

    bundle_key: str
    session_id: str
    company_name: str | None = None
    services: SampleDataServices = Field(default_factory=SampleDataServices)


class PreviewOutputV2(BaseModel):
    """Represents the combined output of the preview generation process.

    This model bundles the workspace generation schema with the corresponding
    sample data payload.
    """

    generation_schema: GenerationSchema
    sample_data: SampleData


class PreviewGeneratorResult(BaseModel):
    """Named result returned by PreviewGeneratorService.generate().

    Carries both the legacy output (generation_json, dummy_data_json) and the
    new ADR-003 output (generation_schema, sample_data) so that PreviewFlow can
    populate AppPayload fields for both during the dual-write migration.

    __iter__ yields (generation_json, dummy_data_json, user_context) so that
    existing tests that unpack with `gen, *_` or `_, dummy, *_uc` continue to
    work without modification.
    """

    generation_json: dict[str, object]
    dummy_data_json: dict[str, object]
    generation_schema: GenerationSchema
    sample_data: SampleData
    user_context: UserContext | None = None

    def __iter__(self) -> Iterator[object | None]:  # type: ignore[override]
        yield self.generation_json
        yield self.dummy_data_json
        yield self.user_context


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
    """Supported edit action types for preview mutation."""

    ADD_MODULE = "add_module"
    REMOVE_MODULE = "remove_module"
    ADD_KPI = "add_kpi"
    REMOVE_KPI = "remove_kpi"
    ADD_DASHBOARD = "add_dashboard"
    REMOVE_DASHBOARD = "remove_dashboard"
    UNSUPPORTED = "unsupported"


class EditAction(BaseModel):
    """Parsed edit instruction consumed by the edit apply step."""

    action_type: EditActionType
    target: str | None = None
    raw_instruction: str = ""
