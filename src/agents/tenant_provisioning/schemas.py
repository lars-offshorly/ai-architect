"""LLM structured-output contract for tenant-provisioning selection.

This module defines the *only* shape the LLM is allowed to produce. The
emitter rejects anything that does not parse cleanly into ``SelectionResult``
and then performs further semantic checks against the catalog (ID existence,
industry equality, etc.).

Mutable surface (per JSONC header):

* ``tenant.*``                     - six fields, freely set
* ``hr_hub.employees[]``           - subset by ID + per-row mutable fields
* ``tickets.queues[]``             - subset by ID
* ``projects.projects[]``          - subset by ID
* ``dashboard.dashboards[]``       - subset by ID
* ``kpi.kpis[]``                   - subset by ID
* ``hr_hub.request_types[]``       - subset by ID

Everything else is frozen and applied by the BE from the catalog.

Design notes:

* Empty arrays are valid (decision 3 from the design review). No
  ``min_length`` constraint at the schema layer.
* ``tenant.industry`` is a free string at this layer. The emitter enforces
  equality against the routing industry once it has the manifest in hand.
* IDs are ``int`` to match the catalog ``id`` field. The schema rejects
  duplicates inside any single list; cross-reference checks (e.g. each
  ``EmployeeOverride.id`` must appear in ``selected_employee_ids``) also
  live here because they are pure schema-internal invariants.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _no_duplicates(values: Sequence[int], field: str) -> list[int]:
    seen: set[int] = set()
    dupes: list[int] = []
    for value in values:
        if value in seen and value not in dupes:
            dupes.append(value)
        seen.add(value)
    if dupes:
        raise ValueError(f"{field} contains duplicate ids: {sorted(dupes)}")
    return list(values)


class TenantSelection(BaseModel):
    """Six tenant-level fields the LLM sets freely (within emitter rules)."""

    model_config = ConfigDict(extra="forbid")

    company_name: str = Field(min_length=1)
    industry: str = Field(min_length=1)
    size_band: str = Field(min_length=1)
    primary_region: str = Field(min_length=1)
    locale: str = Field(min_length=1)
    timezone: str = Field(min_length=1)


class EmployeeOverride(BaseModel):
    """Per-employee mutable fields. ``id`` is a frozen catalog reference."""

    model_config = ConfigDict(extra="forbid")

    id: int = Field(ge=1)
    position: str = Field(min_length=1)
    team: str = Field(min_length=1)
    department: str = Field(min_length=1)
    job_title: str = Field(min_length=1)
    job_type: str = Field(min_length=1)
    job_level: str = Field(min_length=1)


class SelectionResult(BaseModel):
    """Full structured-output payload the LLM emits.

    The emitter consumes this with the loaded JSONC manifest and produces the
    final tenant-provisioning JSON. Validation here is schema-internal only;
    catalog-relative checks (ID exists, industry matches routing) live in the
    emitter where the manifest is available.
    """

    model_config = ConfigDict(extra="forbid")

    tenant: TenantSelection
    selected_queue_ids: list[int] = Field(default_factory=list)
    selected_project_ids: list[int] = Field(default_factory=list)
    selected_dashboard_ids: list[int] = Field(default_factory=list)
    selected_kpi_ids: list[int] = Field(default_factory=list)
    selected_request_type_ids: list[int] = Field(default_factory=list)
    selected_employee_ids: list[int] = Field(default_factory=list)
    employee_overrides: list[EmployeeOverride] = Field(default_factory=list)

    @field_validator(
        "selected_queue_ids",
        "selected_project_ids",
        "selected_dashboard_ids",
        "selected_kpi_ids",
        "selected_request_type_ids",
        "selected_employee_ids",
    )
    @classmethod
    def _reject_duplicate_ids(cls, value: list[int], info: object) -> list[int]:
        field = getattr(info, "field_name", "selected_ids")
        return _no_duplicates(value, field)

    @model_validator(mode="after")
    def _overrides_match_selected_employees(self) -> SelectionResult:
        selected = set(self.selected_employee_ids)
        seen: set[int] = set()
        dupes: list[int] = []
        unknown: list[int] = []
        for override in self.employee_overrides:
            if override.id in seen and override.id not in dupes:
                dupes.append(override.id)
            seen.add(override.id)
            if override.id not in selected:
                unknown.append(override.id)
        if dupes:
            raise ValueError(
                f"employee_overrides has duplicate ids: {sorted(dupes)}"
            )
        if unknown:
            raise ValueError(
                "employee_overrides reference ids not in selected_employee_ids: "
                f"{sorted(unknown)}"
            )
        return self
