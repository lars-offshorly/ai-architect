from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class PersonDetail(BaseModel):
    """A person mentioned in the conversation — employee, team member, or the user themselves."""

    name: Optional[str] = None
    role: Optional[str] = None        # e.g. "Attorney", "Tech Lead"
    department: Optional[str] = None
    is_user: bool = False             # True if this person is the one chatting


class TeamDetail(BaseModel):
    """A team or department mentioned in the conversation."""

    name: str
    size: Optional[int] = None
    function: Optional[str] = None   # e.g. "Engineering", "Litigation"


class WorkItemDetail(BaseModel):
    """A type of work item described in the conversation."""

    name: Optional[str] = None
    work_type: str                    # "sprint" | "litigation" | "waterfall" | "support_request"
    has_deadlines: bool = False
    methodology: Optional[str] = None  # "agile" | "waterfall" | "kanban" | "hybrid"


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

    company_name: Optional[str] = None
    company_size: Optional[str] = None         # "small" | "mid-sized" | "enterprise"
    industry_detail: Optional[str] = None      # more specific than classification.industry
    people: list[PersonDetail] = Field(default_factory=list)
    teams: list[TeamDetail] = Field(default_factory=list)
    work_items: list[WorkItemDetail] = Field(default_factory=list)
    has_remote_teams: Optional[bool] = None
    has_clients: Optional[bool] = None         # external client work vs internal
    work_methodology: Optional[str] = None     # "agile" | "waterfall" | "hybrid"
    primary_concern: Optional[str] = None      # user's main pain point
    key_phrases: list[str] = Field(default_factory=list)  # signal phrases for KPI matching
