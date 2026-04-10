from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Entity relationship model
# ---------------------------------------------------------------------------


class EntityRelationship(BaseModel):
    """A directed relationship between two bundle entities."""

    source_entity: str = Field(description="Source entity key, e.g. 'employee'.")
    target_entity: str = Field(description="Target entity key, e.g. 'leave_request'.")
    relation_type: str = Field(
        description="Relationship type: 'has_many', 'belongs_to', or 'references'."
    )
    label: str | None = Field(
        default=None, description="Human-readable relationship label."
    )

# ---------------------------------------------------------------------------
# Shared primitive: KPI definition item
# ---------------------------------------------------------------------------


class KpiDefinitionItem(BaseModel):
    """A single KPI metric declared in a bundle's config."""

    key: str = Field(description="Stable machine-readable KPI identifier.")
    label: str = Field(description="Human-readable KPI display name.")
    # Sourced from preview generator KPI metric types and bundle catalog metadata.
    # Valid values: "percentage", "count", "duration", "status", "ratio".
    unit: str = Field(description="Display unit suffix, e.g. '%', 'days', 'tickets'.")


# ---------------------------------------------------------------------------
# Bundle-specific config models
# ---------------------------------------------------------------------------


class HrHubConfig(BaseModel):
    """Config sub-schema for the HR Hub bundle (``bundle_key='hr_hub'``)."""

    ticket_categories: list[str] = Field(
        min_length=1,
        description="Valid HR ticket category slugs.",
    )
    default_statuses: list[str] = Field(
        min_length=1,
        description="Ticket lifecycle status slugs in progression order.",
    )
    default_priorities: list[str] = Field(
        min_length=1,
        description="Ticket priority levels in ascending severity order.",
    )
    queue_names: list[str] = Field(
        min_length=1,
        description="Human-readable HR queue labels.",
    )
    kpi_definitions: list[KpiDefinitionItem] = Field(
        min_length=1,
        description="KPI metrics displayed on the HR Hub dashboard.",
    )


class ProjectMgmtConfig(BaseModel):
    """Config sub-schema for the Project Operations bundle"""

    task_statuses: list[str] = Field(
        min_length=1,
        description="Task lifecycle status slugs in progression order.",
    )
    task_priorities: list[str] = Field(
        min_length=1,
        description="Task priority levels in ascending severity order.",
    )
    milestone_statuses: list[str] = Field(
        min_length=1,
        description="Milestone health states.",
    )
    kpi_definitions: list[KpiDefinitionItem] = Field(
        min_length=1,
        description="KPI metrics displayed on the project ops dashboard.",
    )


class TicketingConfig(BaseModel):
    """Config sub-schema for the Field Service bundle"""

    work_order_statuses: list[str] = Field(
        min_length=1,
        description="Work order lifecycle statuses.",
    )
    work_order_priorities: list[str] = Field(
        min_length=1,
        description="Work order priority levels including the emergency tier.",
    )
    service_types: list[str] = Field(
        min_length=1,
        description="Categories of field service activity.",
    )
    kpi_definitions: list[KpiDefinitionItem] = Field(
        min_length=1,
        description="KPI metrics displayed on the field service dashboard.",
    )


class GenericConfig(BaseModel):
    """Config sub-schema for the Generic fallback bundle"""

    ticket_statuses: list[str] = Field(
        min_length=1,
        description="Generic ticket lifecycle status slugs.",
    )
    ticket_priorities: list[str] = Field(
        min_length=1,
        description="Generic ticket priority levels.",
    )
    kpi_definitions: list[KpiDefinitionItem] = Field(
        min_length=1,
        description="KPI metrics displayed on the generic dashboard.",
    )


# ---------------------------------------------------------------------------
# Feature flag item
# ---------------------------------------------------------------------------


class FeatureFlagItem(BaseModel):
    """A single feature flag entry controlling module visibility."""

    id: int = Field(
        description="Stable flag identifier used by the orchestration service.",
    )
    name: str = Field(
        description="Human-readable feature flag name.",
    )
    description: str = Field(
        default="",
        description="Optional explanation of what this flag gates.",
    )
    isEnabled: bool = Field(
        description="True when the feature is active for this workspace.",
    )
    module: str = Field(
        description="Module this flag belongs to, e.g. 'dashboard', 'tickets'.",
    )


# ---------------------------------------------------------------------------
# Bundle config dispatch map (internal)
# ---------------------------------------------------------------------------

_BUNDLE_CONFIG_MODELS: dict[str, type[BaseModel]] = {
    "hr_hub": HrHubConfig,
    "project_mgmt": ProjectMgmtConfig,
    "ticketing": TicketingConfig,
    "generic": GenericConfig,
}

# Public alias so callers can check membership without importing the internal map.
KNOWN_BUNDLE_KEYS: frozenset[str] = frozenset(_BUNDLE_CONFIG_MODELS)


# ---------------------------------------------------------------------------
# Top-level generation_json schema
# ---------------------------------------------------------------------------


class GenerationJsonSchema(BaseModel):
    """Full typed schema for the ``generation_json`` provisioning payload."""

    schema_version: Literal["1.0"] = Field(
        description="Provisioning schema version. Must be '1.0'.",
    )
    bundle_key: str = Field(
        description="Bundle identifier; selects the config sub-schema.",
    )
    display_name: str = Field(
        default="",
        description="Human-readable workspace name shown in the UI.",
    )
    modules: list[str] = Field(
        min_length=1,
        description="Ordered list of module slugs active in this workspace.",
    )
    config: dict[str, object] = Field(
        description="Bundle-specific config dict; validated against the bundle model.",
    )
    feature_flags: list[FeatureFlagItem] = Field(
        default_factory=list,
        description="Orchestration feature flags. Optional; populated by the pipeline.",
    )
    slots_used: list[str] = Field(
        default_factory=list,
        description=(
            "Conversation slot keys applied during personalisation. Informational."
        ),
    )

    @model_validator(mode="after")
    def _validate_bundle_config(self) -> GenerationJsonSchema:
        """Validate ``config`` against the bundle-specific config model.

        Looks up the config model class from ``_BUNDLE_CONFIG_MODELS`` using
        ``self.bundle_key``, then calls ``model_validate`` on ``self.config``.
        Any structural mismatch in ``config`` surfaces as a nested
        ``ValidationError`` with the full field path.

        Raises:
            ValueError: If ``bundle_key`` is not in ``_BUNDLE_CONFIG_MODELS``.
            ValidationError: (propagated from Pydantic) if ``config`` does
                             not satisfy the selected bundle config schema.
        """
        model_cls = _BUNDLE_CONFIG_MODELS.get(self.bundle_key)
        if model_cls is None:
            known = sorted(_BUNDLE_CONFIG_MODELS)
            raise ValueError(
                f"Unknown bundle_key {self.bundle_key!r}. "
                f"Registered bundles: {known}"
            )
        model_cls.model_validate(self.config)
        return self


# ===========================================================================
# dummy_data_json store entity schemas
# ===========================================================================
#
# These models define the shape of every record inside
# ``dummy_data_json.stores``.  They are grounded in two sources:
#
#   1. The five bundle ``dummy_data.json`` template files — minimal, flat
#      records used as static fallbacks.
#   2. ``docs/sample_dummy_data.json`` and ``docs/frontend_data_structure.md``
#      — the full TypeScript entity shapes the frontend actually expects.
#
# Design rule: every non-identifying field is ``Optional`` with a ``None``
# default so that:
#   (a) AI-generated full-shape payloads validate correctly, and
#   (b) simplified template fallbacks also pass validation without errors.
#
# Naming convention:  models are suffixed ``StoreItem`` to distinguish them
# from config-level definitions (``KpiDefinitionItem``) and from internal
# pipeline state models in ``agents.preview_generator.schemas``.
# ===========================================================================


# ---------------------------------------------------------------------------
# Shared store primitives
# ---------------------------------------------------------------------------


class WidgetPosition(BaseModel):
    """Grid position and size of a dashboard widget."""

    row: int = Field(
        description="Zero-based row index of the widget's top-left corner."
    )
    col: int = Field(
        description="Zero-based column index of the widget's top-left corner."
    )
    width: int = Field(ge=1, description="Horizontal span in grid units.")
    height: int = Field(ge=1, description="Vertical span in grid units.")


class DashboardWidgetEntity(BaseModel):
    """A single widget placed on the bundle dashboard."""

    id: str = Field(description="Stable widget identifier within the dashboard.")
    type: str = Field(description="Frontend component slug for this widget.")
    title: str = Field(description="Human-readable widget heading.")
    position: WidgetPosition = Field(description="Grid placement and size.")


class DashboardInfo(BaseModel):
    """Dashboard information in generation response."""

    id: str = Field(description="Generated dashboard ID.")
    name: str = Field(description="Generated dashboard name.")
    url: str | None = Field(default=None, description="Generated dashboard URL.")


class WidgetCount(BaseModel):
    """Widget count breakdown by widget type."""

    text: int = Field(default=0)
    number: int = Field(default=0)
    bar: int = Field(default=0)  # pylint: disable=disallowed-name
    hbar: int = Field(default=0)
    pie: int = Field(default=0)
    line: int = Field(default=0)
    scatter: int = Field(default=0)
    list: int = Field(default=0)
    combo: int = Field(default=0)
    embed: int = Field(default=0)
    total: int = Field(default=0)


class DebugPayload(BaseModel):
    """Debug payload with generated widget details."""

    widgets: list[dict[str, object]] = Field(default_factory=list)
    total_widgets: int = Field(default=0)
    generated_at: str = Field(description="ISO timestamp when widgets were generated.")
    widget_breakdown: WidgetCount


class GenerationMetadata(BaseModel):
    """Metadata describing the generation process."""

    report_length: int = Field(default=0)
    widgets_extracted: int = Field(default=0)
    widgets_explicit: int = Field(default=0)
    data_sources_used: list[str] = Field(default_factory=list)
    processing_steps: list[str] = Field(default_factory=list)


class DashboardGenerateOutput(BaseModel):
    """OpenAPI-aligned dashboard generate response embedded in stores."""

    success: bool = Field(default=True)
    dashboard: DashboardInfo | None = None
    widgets: WidgetCount | None = None
    execution_time: str = Field(default="0m 1s")
    errors: list[str] = Field(default_factory=list)
    debug_payload: DebugPayload | None = None
    generation_metadata: GenerationMetadata | None = None


class KpiStoreItem(BaseModel):
    """A KPI record inside ``stores.kpis``."""

    id: int | str = Field(
        description="Record identifier (int in full form, str slug in templates)."
    )

    # Simple template form fields
    label: str | None = Field(
        default=None, description="Display label used in the simple template form."
    )
    value: int | float | None = Field(
        default=None, description="Current numeric value (simple form)."
    )
    unit: str | None = Field(
        default=None, description="Display unit suffix (simple form)."
    )
    trend: str | None = Field(
        default=None, description="Direction indicator: 'up', 'down', or 'stable'."
    )

    # Full frontend form fields
    name: str | None = Field(
        default=None, description="KPI display name (full frontend form)."
    )
    type: str | None = Field(
        default=None, description="'Quantitative' or 'Qualitative'."
    )
    status: str | None = Field(
        default=None, description="'Ongoing', 'Completed', or 'Not Started'."
    )
    frequency: str | None = Field(
        default=None, description="Measurement cadence, e.g. 'Monthly'."
    )
    assesseeType: str | None = Field(
        default=None, description="'Teams' or 'Individuals'."
    )
    assessees: list[str] = Field(
        default_factory=list, description="Names of teams or individuals assessed."
    )
    category: str | None = Field(default=None, description="KPI grouping category.")
    startDate: str | None = Field(
        default=None, description="ISO 8601 period start datetime."
    )
    endDate: str | None = Field(
        default=None, description="ISO 8601 period end datetime."
    )
    qualitativeType: str | None = Field(
        default=None, description="Sub-type for qualitative KPIs."
    )
    isMandatory: bool | None = Field(
        default=None, description="Whether a response is required."
    )
    isDataEntryRemarksEnabled: bool | None = Field(
        default=None, description="Whether remarks are allowed during data entry."
    )
    evaluatorsHidden: bool | None = Field(
        default=None, description="Whether evaluator identities are hidden."
    )
    evaluatorsSeeOverallResults: bool | None = Field(
        default=None, description="Whether evaluators see aggregate results."
    )
    details: dict[str, object] | None = Field(
        default=None,
        description=(
            "Quantitative KPI detail sub-schema. Expected keys: target, thresholds, "
            "condition, dataLabel, customDataLabel, numberFormat, resultType."
        ),
    )
    owner: str | None = Field(default=None, description="KPI owner identifier.")
    kpiAssessees: list[dict[str, object]] = Field(
        default_factory=list, description="Structured assessee records."
    )
    kpiUsers: list[dict[str, object]] = Field(
        default_factory=list, description="KPI user assignment records."
    )
    currentUser: list[dict[str, object]] = Field(
        default_factory=list, description="Current user association records."
    )
    createdAt: str | None = Field(
        default=None, description="ISO 8601 creation timestamp."
    )
    updatedAt: str | None = Field(
        default=None, description="ISO 8601 last-updated timestamp."
    )


# ---------------------------------------------------------------------------
# Ticket store entities
# ---------------------------------------------------------------------------


class TicketStatusObject(BaseModel):
    """Nested status object on a ``TicketStoreItem``."""

    id: int = Field(description="Integer identifier for the status record.")
    name: str = Field(description="Human-readable status name, e.g. 'Open'.")
    slug: str = Field(description="Machine-readable slug, e.g. 'open'.")
    status: str = Field(description="Status string; mirrors slug in practice.")
    description: str = Field(
        default="", description="Optional explanation of the status."
    )
    color: str = Field(default="", description="Hex color code for the status badge.")
    icon: str | None = Field(default=None, description="Optional icon identifier.")
    deletedAt: str | None = Field(
        default=None, description="ISO 8601 soft-delete timestamp."
    )


class TicketAssigneeRef(BaseModel):
    """A lightweight reference to an assignee on a ticket."""

    userId: int = Field(description="Integer user identifier in the HR/auth system.")


class TicketAuthorDetails(BaseModel):
    """Author (submitter) details embedded on a ``TicketStoreItem``."""

    firstName: str = Field(description="Submitter's first name.")
    lastName: str = Field(description="Submitter's last name.")
    userId: int = Field(description="Integer user identifier in the HR/auth system.")


class TicketStoreItem(BaseModel):
    """A ticket record inside ``stores.tickets``."""

    id: int | str = Field(
        description="Record identifier (int in full form, str slug in templates)."
    )

    # Core required fields
    title: str = Field(description="Ticket subject line.")
    description: str = Field(default="", description="Full ticket body text.")

    # Status — accepts nested object (full form) or plain string (template form)
    status: TicketStatusObject | str | None = Field(
        default=None,
        description=(
            "TicketStatusObject (full form) or status slug string (template form)."
        ),
    )

    # Assignee — accepts list of refs (full form) or plain string (template form)
    assignee: list[TicketAssigneeRef] | str | None = Field(
        default=None,
        description=(
            "List of TicketAssigneeRef (full form) or assignee name string"
            " (template form)."
        ),
    )

    # Full-form specific fields
    ticketId: str | None = Field(
        default=None,
        description="Human-readable ticket reference code, e.g. 'TCK-1001'.",
    )
    authorDetails: TicketAuthorDetails | None = Field(
        default=None, description="Submitter name and userId (full form)."
    )
    priorityDescription: str | None = Field(
        default=None, description="Prose description of the priority level."
    )
    subCategory: str | None = Field(default=None, description="Optional sub-category.")
    requestType: str | None = Field(
        default=None, description="Optional request type label."
    )
    impact: int | None = Field(default=None, description="Integer impact score (1–5).")
    urgency: int | None = Field(
        default=None, description="Integer urgency score (1–5)."
    )
    emailSubmitter: list[str] = Field(
        default_factory=list, description="Email addresses that submitted via email."
    )
    createdFromEmail: str | None = Field(
        default=None, description="Source email address if email-created."
    )
    conversationEmail: str | None = Field(
        default=None, description="Reply-to email address for this ticket thread."
    )
    formId: int | None = Field(
        default=None, description="ID of the form used to submit."
    )
    formName: str | None = Field(
        default=None, description="Name of the form used to submit."
    )
    form: dict[str, object] | None = Field(
        default=None, description="Full form object."
    )
    submission: dict[str, object] | None = Field(
        default=None, description="Form submission data."
    )
    submittedBy: int | None = Field(
        default=None, description="User ID of the submitter."
    )
    account: str | None = Field(
        default=None, description="Account or department label."
    )
    icon: str | None = Field(default=None, description="Optional icon identifier.")

    # Shared optional fields
    priority: str | None = Field(
        default=None, description="Priority label, e.g. 'high', 'High'."
    )
    category: str | None = Field(default=None, description="Ticket category slug.")
    queue: str | None = Field(default=None, description="Queue assignment.")
    dueDate: str | None = Field(default=None, description="ISO 8601 due date.")

    # Timestamps — two naming conventions used across the codebase
    createdAt: str | None = Field(
        default=None, description="ISO 8601 creation timestamp (camelCase)."
    )
    created_at: str | None = Field(
        default=None,
        description="ISO 8601 creation timestamp (snake_case, template form).",
    )

    # Template-form specific fields
    requester: str | None = Field(
        default=None, description="Submitter name string (template form)."
    )


# ---------------------------------------------------------------------------
# Project and Task store entities
# ---------------------------------------------------------------------------


class TaskParentRef(BaseModel):
    """A lightweight parent reference embedded in a ``TaskStoreItem``."""

    id: str | int | None = Field(default=None, description="Parent record identifier.")
    name: str | None = Field(default=None, description="Parent display name.")


class ProjectStoreItem(BaseModel):
    """A project record inside ``stores.projects`` (Project Ops bundle)."""

    id: str | int = Field(description="Project identifier.")
    name: str = Field(description="Project display name.")
    description: str | None = Field(
        default=None, description="Optional project description."
    )
    progress: int | None = Field(
        default=None, ge=0, le=100, description="Completion percentage (0–100)."
    )
    isFavorite: bool = Field(
        default=False, description="Whether the project is starred by the current user."
    )
    assignedTo: list[dict[str, object]] = Field(
        default_factory=list, description="Assigned user records."
    )
    adminUsers: list[dict[str, object]] = Field(
        default_factory=list, description="Admin user records."
    )
    startDate: str | None = Field(
        default=None, description="ISO 8601 project start date."
    )
    endDate: str | None = Field(default=None, description="ISO 8601 project end date.")


class TaskStoreItem(BaseModel):
    """A task record inside ``stores.tasks`` (Project Ops bundle)."""

    id: str | int = Field(description="Task identifier.")

    # Name — two aliases used across the codebase
    taskName: str | None = Field(
        default=None, description="Task display name (full frontend form)."
    )
    title: str | None = Field(
        default=None, description="Task display name (simple template form)."
    )

    # Project linkage
    projectId: str | int | None = Field(
        default=None, description="ID of the parent project."
    )
    project: str | None = Field(
        default=None, description="Parent project name string (template form)."
    )

    status: str | None = Field(default=None, description="Status slug or label.")
    priority: str | None = Field(
        default=None, description="Priority level slug (template form)."
    )
    progress: int | None = Field(
        default=None, ge=0, le=100, description="Completion percentage (0–100)."
    )

    # Assignee — list in full form, string in template form
    assignedTo: list[dict[str, object]] = Field(
        default_factory=list, description="Assigned user records (full form)."
    )
    assignee: str | None = Field(
        default=None, description="Assignee name string (template form)."
    )

    # Full frontend form fields
    taskDuration: int | None = Field(
        default=None, description="Estimated duration in days."
    )
    isSubtask: int | None = Field(
        default=None, description="1 if subtask, 0 if root task."
    )
    subtasksCount: int | None = Field(
        default=None, description="Number of child subtasks."
    )
    taskDependenciesCount: int | None = Field(
        default=None, description="Number of task dependencies."
    )
    commentsCount: int | None = Field(default=None, description="Number of comments.")
    attachmentsCount: int | None = Field(
        default=None, description="Number of file attachments."
    )
    isFavorite: bool | None = Field(
        default=None, description="Whether the task is starred."
    )
    parentProject: TaskParentRef | None = Field(
        default=None, description="Lightweight parent project reference."
    )
    parentTask: TaskParentRef | None = Field(
        default=None, description="Lightweight parent task reference."
    )
    taskDependencies: list[dict[str, object]] = Field(
        default_factory=list, description="Dependency records."
    )
    taskLink: list[dict[str, object]] = Field(
        default_factory=list, description="Linked task records."
    )
    taskTimeSpent: dict[str, object] | None = Field(
        default=None, description="Time tracking record."
    )
    lastTaskActivity: dict[str, object] | None = Field(
        default=None, description="Last activity record."
    )
    timelineColorSettings: dict[str, object] | None = Field(
        default=None, description="Timeline colour config."
    )
    timelineTypographySettings: dict[str, object] | None = Field(
        default=None, description="Timeline typography config."
    )
    customFields: list[dict[str, object]] = Field(
        default_factory=list, description="Custom field records."
    )

    # Timestamps — two naming conventions
    createdAt: str | None = Field(
        default=None, description="ISO 8601 creation timestamp (camelCase)."
    )
    updatedAt: str | None = Field(
        default=None, description="ISO 8601 last-updated timestamp (camelCase)."
    )
    due_date: str | None = Field(
        default=None, description="ISO 8601 due date (snake_case, template form)."
    )


# ---------------------------------------------------------------------------
# Milestone store entity (Project Ops)
# ---------------------------------------------------------------------------


class MilestoneStoreItem(BaseModel):
    """A milestone record inside ``stores.milestones`` (Project Ops bundle)."""

    id: str | int = Field(description="Milestone identifier.")
    name: str = Field(description="Milestone display name.")
    status: str | None = Field(
        default=None,
        description="Health state slug: 'pending', 'at_risk', or 'achieved'.",
    )
    target_date: str | None = Field(
        default=None, description="ISO 8601 target completion date."
    )
    project: str | None = Field(default=None, description="Name of the parent project.")


# ---------------------------------------------------------------------------
# Employee store entity (HR Hub)
# Primary entity per bundle_registry.yaml: primary_entity='people'
# entity_definitions: employee, leave_request, department
# ---------------------------------------------------------------------------


class EmployeeStoreItem(BaseModel):
    """An employee record inside ``stores.employees`` (HR Hub bundle).

    Represents the primary entity of the ``hr_management`` catalog bundle
    (render key ``hr_hub``). Shape is informed by the ``/employees/me``
    response in ``docs/api-mocks.json`` and the YAML ``entity_definitions``.
    All fields beyond ``id`` are optional to support both minimal template
    records and full HR system records.
    """

    id: int | str = Field(description="Employee record identifier.")
    firstName: str | None = Field(default=None, description="Employee's first name.")
    lastName: str | None = Field(default=None, description="Employee's last name.")
    position: str | None = Field(
        default=None, description="Job title or position label."
    )
    department: str | None = Field(default=None, description="Department or team name.")
    status: str | None = Field(
        default=None,
        description="Attendance/availability status, e.g. 'Active', 'Absent'.",
    )
    employmentStatus: str | None = Field(
        default=None,
        description="Employment lifecycle state, e.g. 'Active', 'Inactive'.",
    )
    team: str | None = Field(
        default=None, description="Team name within the department."
    )
    userId: int | None = Field(
        default=None, description="Linked user ID in the orchestration service."
    )


# ---------------------------------------------------------------------------
# Queue store entity (HR Hub and Ticketing)
# ---------------------------------------------------------------------------


class QueueStoreItem(BaseModel):
    """A queue record inside ``stores.queues``."""

    id: str | int = Field(description="Queue identifier.")
    name: str = Field(description="Human-readable queue label.")
    ticket_count: int | None = Field(
        default=None, description="Number of open tickets in the queue."
    )
    avg_resolution_days: float | int | None = Field(
        default=None, description="Rolling average resolution time in days."
    )


# ---------------------------------------------------------------------------
# Agent store entity (Ticketing)
# entity_definitions: ticket, queue, agent (bundle_registry.yaml)
# ---------------------------------------------------------------------------


class AgentStoreItem(BaseModel):
    """An agent record inside ``stores.agents`` (Ticketing bundle).

    Represents a support agent who handles tickets within queues.
    Defined as a primary entity of the ``ticketing`` catalog bundle
    per ``bundle_registry.yaml`` ``entity_definitions``.
    """

    id: int | str = Field(description="Agent record identifier.")
    name: str | None = Field(default=None, description="Agent's display name.")
    email: str | None = Field(default=None, description="Agent's work email address.")
    queue: str | None = Field(
        default=None, description="Name of the primary queue this agent is assigned to."
    )
    status: str | None = Field(
        default=None,
        description="Availability status, e.g. 'available', 'busy', 'offline'.",
    )
    ticket_count: int | None = Field(
        default=None,
        description="Number of open tickets currently assigned to this agent.",
    )
    userId: int | None = Field(
        default=None, description="Linked user ID in the orchestration service."
    )


# ---------------------------------------------------------------------------
# Weave store entity (Project Ops and HR Hub)
# ---------------------------------------------------------------------------


class WeaveAttributes(BaseModel):
    """Visual and format attributes of a Weave (spreadsheet) entity."""

    format: str | None = Field(
        default=None, description="File format of the sheet, e.g. 'xlsx'."
    )
    sheetsSort: list[object] | None = Field(
        default=None, description="Sheet ordering metadata."
    )
    jobs: list[object] | None = Field(
        default=None, description="Background jobs associated with this weave."
    )


class WeaveStoreItem(BaseModel):
    """A Weave (spreadsheet) record inside ``stores.weaves``.

    Shape matches the ``/weaves`` mock endpoint (``api-mocks.json``).
    """

    id: str | int = Field(description="Weave identifier.")
    name: str = Field(description="Weave display name.")
    description: str | None = Field(
        default=None, description="Optional description of the spreadsheet's purpose."
    )
    authorId: int | None = Field(
        default=None, description="User ID of the weave creator."
    )
    shared: bool | None = Field(
        default=None, description="True when the weave is shared with the workspace."
    )
    activeSheetId: str | None = Field(
        default=None, description="ID of the currently active sheet."
    )
    archived: bool | None = Field(
        default=None, description="True when the weave is archived."
    )
    favorite: bool | None = Field(
        default=None, description="True when the weave is starred by the owner."
    )
    attributes: WeaveAttributes | None = Field(
        default=None, description="Visual and format attributes."
    )
    createdAt: str | None = Field(
        default=None, description="ISO 8601 creation timestamp."
    )
    updatedAt: str | None = Field(
        default=None, description="ISO 8601 last-updated timestamp."
    )
    lastViewedAt: str | None = Field(
        default=None, description="ISO 8601 most-recent-view timestamp."
    )
    deletedAt: str | None = Field(
        default=None, description="ISO 8601 soft-delete timestamp; null when active."
    )


# ---------------------------------------------------------------------------
# Bundle-specific store container models
# ---------------------------------------------------------------------------


class HrHubStores(BaseModel):
    """Store container for the HR Hub bundle (``bundle_key='hr_hub'``).

    Primary entity per ``bundle_registry.yaml``: ``people``.
    Entity definitions: ``employee``, ``leave_request``, ``department``.

    ``employees`` is the YAML primary entity store.
    ``tickets`` holds HR requests (leave, onboarding, policy) as work items.
    ``queues`` groups HR requests by category (Leave Requests, Onboarding, etc.).
    """

    employees: list[EmployeeStoreItem] = Field(
        default_factory=list,
        description="Employee records. Primary entity for the HR Hub bundle.",
    )
    tickets: list[TicketStoreItem] = Field(
        default_factory=list,
        description="HR request records (leave, onboarding, policy questions).",
    )
    queues: list[QueueStoreItem] = Field(default_factory=list)
    kpis: list[KpiStoreItem] = Field(default_factory=list)
    dashboard_widgets: list[DashboardWidgetEntity] = Field(default_factory=list)
    dashboard_generation_output: DashboardGenerateOutput | None = None


class ProjectMgmtStores(BaseModel):
    """Store container for the Project Management bundle
    (``bundle_key='project_mgmt'``).
    """

    tasks: list[TaskStoreItem] = Field(default_factory=list)
    milestones: list[MilestoneStoreItem] = Field(default_factory=list)
    kpis: list[KpiStoreItem] = Field(default_factory=list)
    dashboard_widgets: list[DashboardWidgetEntity] = Field(default_factory=list)
    dashboard_generation_output: DashboardGenerateOutput | None = None
    projects: list[ProjectStoreItem] = Field(default_factory=list)
    weaves: list[WeaveStoreItem] = Field(default_factory=list)


class TicketingStores(BaseModel):
    """Store container for the Ticketing bundle (``bundle_key='ticketing'``).

    Primary entity per ``bundle_registry.yaml``: ``ticket``.
    Entity definitions: ``ticket``, ``queue``, ``agent``.
    Covers catalog bundles: ``ticketing``, ``healthcare``, ``legal_services``.

    ``tickets`` is the YAML primary entity store.
    ``queues`` routes tickets to the correct handling team.
    ``agents`` are the support staff assigned to resolve tickets.
    """

    tickets: list[TicketStoreItem] = Field(
        default_factory=list,
        description="Ticket records. Primary entity for the Ticketing bundle.",
    )
    queues: list[QueueStoreItem] = Field(
        default_factory=list,
        description="Queue records routing tickets to handling teams.",
    )
    agents: list[AgentStoreItem] = Field(
        default_factory=list,
        description="Agent records assigned to resolve tickets within queues.",
    )
    kpis: list[KpiStoreItem] = Field(default_factory=list)
    dashboard_widgets: list[DashboardWidgetEntity] = Field(default_factory=list)
    dashboard_generation_output: DashboardGenerateOutput | None = None


class GenericStores(BaseModel):
    """Store container for the Generic fallback bundle
    (``bundle_key='generic'``).
    """

    tickets: list[TicketStoreItem] = Field(default_factory=list)
    kpis: list[KpiStoreItem] = Field(default_factory=list)
    dashboard_widgets: list[DashboardWidgetEntity] = Field(default_factory=list)
    dashboard_generation_output: DashboardGenerateOutput | None = None


# ---------------------------------------------------------------------------
# Bundle stores dispatch map (internal)
# ---------------------------------------------------------------------------

_BUNDLE_STORES_MODELS: dict[str, type[BaseModel]] = {
    "hr_hub": HrHubStores,
    "project_mgmt": ProjectMgmtStores,
    "ticketing": TicketingStores,
    "generic": GenericStores,
}


# ---------------------------------------------------------------------------
# Top-level dummy_data_json schema
# ---------------------------------------------------------------------------


class DummyDataJsonSchema(BaseModel):
    """Full typed schema for the ``dummy_data_json`` provisioning payload."""

    schema_version: Literal["1.0"] = Field(
        description="Provisioning schema version. Must be '1.0'.",
    )
    bundle_key: str = Field(
        description="Bundle identifier; selects the stores container sub-schema.",
    )
    session_id: str = Field(
        description="UUID string identifying the onboarding session.",
    )
    company_name: str | None = Field(
        default=None,
        description="Company name extracted from the conversation for personalisation.",
    )
    stores: dict[str, object] = Field(
        description=(
            "Bundle-specific store dict; validated against the bundle stores model."
        ),
    )

    @model_validator(mode="after")
    def _validate_bundle_stores(self) -> DummyDataJsonSchema:
        """Validate ``stores`` against the bundle-specific stores container.

        Looks up the stores model class from ``_BUNDLE_STORES_MODELS`` using
        ``self.bundle_key``, then calls ``model_validate`` on ``self.stores``.
        Any structural mismatch in a store array surfaces as a nested
        ``ValidationError`` with the full field path (e.g.
        ``stores.tickets[0].status``).

        Raises:
            ValueError: If ``bundle_key`` is not in ``_BUNDLE_STORES_MODELS``.
            ValidationError: (propagated from Pydantic) if ``stores`` does
                             not satisfy the selected bundle stores schema.
        """
        model_cls = _BUNDLE_STORES_MODELS.get(self.bundle_key)
        if model_cls is None:
            known = sorted(_BUNDLE_STORES_MODELS)
            raise ValueError(
                f"Unknown bundle_key {self.bundle_key!r}. "
                f"Registered bundles: {known}"
            )
        model_cls.model_validate(self.stores)
        return self
