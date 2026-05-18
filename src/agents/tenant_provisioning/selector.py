"""Selector interface + deterministic baseline implementation.

A *selector* takes a ``CatalogView`` plus a free-text user request and returns
a ``SelectionResult``. The runtime selector will eventually be LLM-backed;
this module defines the contract and a non-LLM baseline that is safe to use
as a default in tests and as a placeholder until the LLM path lands.

The baseline picks **everything** from the catalog and copies the manifest's
tenant defaults verbatim, applying only the explicit ``tenant_overrides``
passed in. That makes it:

* deterministic (no model, no I/O),
* trivially testable (output is a pure function of inputs),
* honest: it never invents catalog IDs or guesses tenant fields.

The LLM selector lands as a separate implementation behind the same
``BundleSelector`` protocol.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .catalog_view import CatalogView
from .schemas import EmployeeOverride, SelectionResult, TenantSelection


class BundleSelector(Protocol):
    """Anything that can turn a CatalogView + user request into a SelectionResult."""

    def select(
        self, catalog_view: CatalogView, user_message: str
    ) -> SelectionResult: ...


@dataclass(slots=True)
class BaselineSelector:
    """Non-LLM selector. Picks everything; only tenant overrides take effect.

    ``tenant_overrides`` is merged on top of the manifest's tenant defaults.
    Unknown keys are ignored at the schema layer; ``industry`` is silently
    locked to the catalog view's bundle industry (decision 1) so that even
    if a caller supplies a mismatched industry, the emitter accepts the
    output.
    """

    tenant_overrides: dict[str, str] | None = None

    def select(
        self, catalog_view: CatalogView, user_message: str
    ) -> SelectionResult:
        _ = user_message  # baseline ignores the message; placeholder until LLM lands

        tenant_fields = dict(catalog_view.tenant_defaults)
        if self.tenant_overrides:
            tenant_fields.update(self.tenant_overrides)
        tenant_fields["industry"] = catalog_view.bundle_industry

        tenant = TenantSelection.model_validate(tenant_fields)

        return SelectionResult(
            tenant=tenant,
            selected_queue_ids=[item.id for item in catalog_view.queues],
            selected_project_ids=[item.id for item in catalog_view.projects],
            selected_dashboard_ids=[item.id for item in catalog_view.dashboards],
            selected_kpi_ids=[item.id for item in catalog_view.kpis],
            selected_request_type_ids=[item.id for item in catalog_view.request_types],
            selected_employee_ids=[emp.id for emp in catalog_view.employees],
            employee_overrides=[
                EmployeeOverride(
                    id=emp.id,
                    position=emp.position,
                    team=emp.team,
                    department=emp.department,
                    job_title=emp.job_title,
                    job_type=emp.job_type,
                    job_level=emp.job_level,
                )
                for emp in catalog_view.employees
            ],
        )
