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
from typing import Any, Protocol

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from .catalog_view import CatalogView
from .schemas import EmployeeOverride, SelectionResult, TenantSelection

_SELECTOR_SYSTEM_PROMPT = """
You are a tenant-provisioning selector for workspace onboarding.

Your job is to return ONLY structured output that matches the SelectionResult schema.

Rules:
1) Only select IDs that exist in the provided catalog.
2) Use the user request to personalize tenant fields and optional employee overrides.
3) Keep tenant.industry aligned with the routing-locked bundle industry
   from the catalog.
4) If uncertain, prefer catalog defaults and conservative selections.
5) Do not invent IDs, fields, or values outside the schema.
""".strip()


class BundleSelector(Protocol):
    """Anything that can turn a CatalogView + user request into a SelectionResult."""

    def select(
        self, catalog_view: CatalogView, user_message: str
    ) -> SelectionResult: ...

    async def select_async(
        self, catalog_view: CatalogView, user_message: str
    ) -> SelectionResult: ...


@dataclass(slots=True)
class LLMSelector:
    """LLM-backed selector with structured-output validation and safe fallback."""

    model: ChatOpenAI
    fallback_selector: BundleSelector | None = None

    def select(self, catalog_view: CatalogView, user_message: str) -> SelectionResult:
        if self.fallback_selector is not None:
            return self.fallback_selector.select(catalog_view, user_message)
        return BaselineSelector().select(catalog_view, user_message)

    async def select_async(
        self, catalog_view: CatalogView, user_message: str
    ) -> SelectionResult:
        structured = self._model_with_schema()
        prompt_context = catalog_view.to_prompt()
        user_prompt = (
            "User request:\n"
            f"{user_message}\n\n"
            "Catalog:\n"
            f"{prompt_context}\n"
            "Return the best SelectionResult."
        )
        try:
            result = await structured.ainvoke(
                [
                    SystemMessage(content=_SELECTOR_SYSTEM_PROMPT),
                    HumanMessage(content=user_prompt),
                ]
            )
            selection = (
                result
                if isinstance(result, SelectionResult)
                else SelectionResult.model_validate(result)
            )
            # Enforce routing lock even if model drifts.
            if selection.tenant.industry != catalog_view.bundle_industry:
                selection = selection.model_copy(
                    update={
                        "tenant": selection.tenant.model_copy(
                            update={"industry": catalog_view.bundle_industry}
                        )
                    }
                )
            return selection
        except (RuntimeError, ValueError, TypeError):
            if self.fallback_selector is not None:
                return self.fallback_selector.select(catalog_view, user_message)
            return BaselineSelector().select(catalog_view, user_message)

    def _model_with_schema(self) -> Any:
        return self.model.with_structured_output(
            SelectionResult, method="function_calling"
        )


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

    async def select_async(
        self, catalog_view: CatalogView, user_message: str
    ) -> SelectionResult:
        return self.select(catalog_view, user_message)

    def select(self, catalog_view: CatalogView, user_message: str) -> SelectionResult:
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
