"""Deterministic manifest -> prompt-context summariser.

The selector LLM is shown a flattened view of the canonical JSONC manifest:

* tenant defaults (for reference / industry equality)
* every catalog item (id + name) in each subset-able array
* every catalog employee (id + current mutable fields, as a starting point)

The output is a stable dataclass plus a ``to_prompt()`` rendering helper. The
LLM never sees the JSONC source directly; it works against this projection,
so the only IDs it can choose from are the ones we surface here.

This module is intentionally pure and side-effect-free. No I/O, no network,
no logging. It exists so the prompt surface is testable in isolation and so
the selector can be reasoned about without loading manifests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True, frozen=True)
class CatalogItem:
    """A single referenceable catalog entry (queue, project, dashboard, KPI, RT)."""

    id: int
    name: str


@dataclass(slots=True, frozen=True)
class CatalogEmployee:
    """Catalog employee row with current mutable defaults from the manifest."""

    id: int
    position: str
    team: str
    department: str
    job_title: str
    job_type: str
    job_level: str


@dataclass(slots=True, frozen=True)
# pylint: disable=too-many-instance-attributes
class CatalogView:
    """Flattened, prompt-ready projection of a canonical manifest.

    ``bundle_industry`` is the manifest's ``tenant.industry`` value. The
    selector should treat it as the routing-locked value (decision 1: tenant
    industry must equal routing industry).

    ``tenant_defaults`` is the full ``tenant`` block from the manifest, useful
    both for showing the LLM sensible starting values and for the emitter to
    diff against.
    """

    bundle_industry: str
    tenant_defaults: dict[str, str]
    queues: list[CatalogItem] = field(default_factory=list)
    projects: list[CatalogItem] = field(default_factory=list)
    dashboards: list[CatalogItem] = field(default_factory=list)
    kpis: list[CatalogItem] = field(default_factory=list)
    request_types: list[CatalogItem] = field(default_factory=list)
    employees: list[CatalogEmployee] = field(default_factory=list)

    @classmethod
    def from_manifest(cls, manifest: dict[str, Any]) -> CatalogView:
        """Project a loaded JSONC manifest into a CatalogView.

        Raises ``ValueError`` if the manifest is missing required structure.
        The registry layer already validates minimum shape, so this is a
        defensive second pass that turns silent ``None`` paths into loud
        errors before they reach the LLM prompt.
        """
        tenant = _require_dict(manifest, "tenant")
        industry = tenant.get("industry")
        if not isinstance(industry, str) or not industry.strip():
            raise ValueError("manifest tenant.industry is required")

        tenant_defaults: dict[str, str] = {}
        for key in (
            "company_name",
            "industry",
            "size_band",
            "primary_region",
            "locale",
            "timezone",
        ):
            value = tenant.get(key)
            if isinstance(value, str):
                tenant_defaults[key] = value

        queues = _collect_items(manifest, "tickets", "queues")
        projects = _collect_items(manifest, "projects", "projects")
        dashboards = _collect_items(manifest, "dashboard", "dashboards")
        kpis = _collect_items(manifest, "kpi", "kpis")

        hr_hub = _require_dict(manifest, "hr_hub")
        request_types = _collect_items({"hr_hub": hr_hub}, "hr_hub", "request_types")
        employees = _collect_employees(hr_hub)

        return cls(
            bundle_industry=industry,
            tenant_defaults=tenant_defaults,
            queues=queues,
            projects=projects,
            dashboards=dashboards,
            kpis=kpis,
            request_types=request_types,
            employees=employees,
        )

    def to_prompt(self) -> str:
        """Render a stable, human-readable menu for the LLM prompt.

        Format is intentionally minimal: section headers + ``id - name``
        rows. Order matches insertion order from the JSONC (the registry
        preserves it via ``json.loads``). Re-rendering the same view always
        produces byte-identical output, which keeps prompts cache-friendly.
        """
        lines: list[str] = []

        lines.append(f"Industry: {self.bundle_industry}")
        lines.append("Tenant defaults:")
        for key, value in self.tenant_defaults.items():
            lines.append(f"  {key}: {value}")
        lines.append("")

        for header, items in (
            ("Available queues", self.queues),
            ("Available projects", self.projects),
            ("Available dashboards", self.dashboards),
            ("Available KPIs", self.kpis),
            ("Available HR request types", self.request_types),
        ):
            lines.append(f"{header}:")
            if not items:
                lines.append("  (none)")
            for item in items:
                lines.append(f"  {item.id} - {item.name}")
            lines.append("")

        lines.append("Catalog employees (id + current mutable defaults):")
        if not self.employees:
            lines.append("  (none)")
        for emp in self.employees:
            lines.append(
                f"  {emp.id}: position={emp.position!r} team={emp.team!r} "
                f"department={emp.department!r} job_title={emp.job_title!r} "
                f"job_type={emp.job_type!r} job_level={emp.job_level!r}"
            )

        return "\n".join(lines).rstrip() + "\n"


def _require_dict(parent: dict[str, Any], key: str) -> dict[str, Any]:
    value = parent.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"manifest {key!r} must be an object")
    return value


def _collect_items(
    parent: dict[str, Any], section: str, array_key: str
) -> list[CatalogItem]:
    block = _require_dict(parent, section)
    raw = block.get(array_key)
    if not isinstance(raw, list):
        raise ValueError(f"manifest {section}.{array_key} must be a list")
    items: list[CatalogItem] = []
    for index, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise ValueError(f"{section}.{array_key}[{index}] must be an object")
        entry_id = entry.get("id")
        name = entry.get("name")
        if not isinstance(entry_id, int):
            raise ValueError(f"{section}.{array_key}[{index}].id must be an int")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(
                f"{section}.{array_key}[{index}].name must be a non-empty string"
            )
        items.append(CatalogItem(id=entry_id, name=name))
    return items


def _collect_employees(hr_hub: dict[str, Any]) -> list[CatalogEmployee]:
    raw = hr_hub.get("employees")
    if not isinstance(raw, list):
        raise ValueError("manifest hr_hub.employees must be a list")
    employees: list[CatalogEmployee] = []
    for index, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise ValueError(f"hr_hub.employees[{index}] must be an object")
        emp_id = entry.get("id")
        if not isinstance(emp_id, int):
            raise ValueError(f"hr_hub.employees[{index}].id must be an int")
        fields: dict[str, str] = {}
        for key in (
            "position",
            "team",
            "department",
            "job_title",
            "job_type",
            "job_level",
        ):
            value = entry.get(key)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"hr_hub.employees[{index}].{key} must be a non-empty string"
                )
            fields[key] = value
        employees.append(CatalogEmployee(id=emp_id, **fields))
    return employees
