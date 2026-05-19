from __future__ import annotations

import pytest

from agents.tenant_provisioning import BaselineSelector, CatalogView, LLMSelector
from agents.tenant_provisioning.catalog_view import CatalogEmployee, CatalogItem


def _view() -> CatalogView:
    return CatalogView(
        bundle_industry="bpo_contact_center",
        tenant_defaults={
            "company_name": "Manifest Defaults Co",
            "industry": "bpo_contact_center",
            "size_band": "50-200",
            "primary_region": "APAC",
            "locale": "en-PH",
            "timezone": "Asia/Manila",
        },
        queues=[CatalogItem(id=101, name="Care"), CatalogItem(id=102, name="Billing")],
        projects=[CatalogItem(id=501, name="P1")],
        dashboards=[CatalogItem(id=701, name="Ops")],
        kpis=[CatalogItem(id=1, name="ART"), CatalogItem(id=2, name="SLA")],
        request_types=[CatalogItem(id=801, name="Leave")],
        employees=[
            CatalogEmployee(
                id=1,
                position="Director",
                team="Ops",
                department="Operations",
                job_title="Director",
                job_type="Full-Time",
                job_level="Director",
            ),
        ],
    )


def test_baseline_selects_everything_and_uses_manifest_tenant_defaults() -> None:
    sel = BaselineSelector().select(_view(), user_message="ignored")
    assert sel.tenant.company_name == "Manifest Defaults Co"
    assert sel.tenant.industry == "bpo_contact_center"
    assert sel.selected_queue_ids == [101, 102]
    assert sel.selected_project_ids == [501]
    assert sel.selected_dashboard_ids == [701]
    assert sel.selected_kpi_ids == [1, 2]
    assert sel.selected_request_type_ids == [801]
    assert sel.selected_employee_ids == [1]
    assert sel.employee_overrides[0].position == "Director"


def test_baseline_applies_tenant_overrides_but_locks_industry() -> None:
    overrides = {
        "company_name": "Override Co",
        "size_band": "1000+",
        "industry": "ignored_value",  # should be locked to view.bundle_industry
    }
    sel = BaselineSelector(tenant_overrides=overrides).select(
        _view(), user_message=""
    )
    assert sel.tenant.company_name == "Override Co"
    assert sel.tenant.size_band == "1000+"
    assert sel.tenant.industry == "bpo_contact_center"


def test_baseline_is_pure_and_repeatable() -> None:
    view = _view()
    a = BaselineSelector().select(view, "msg")
    b = BaselineSelector().select(view, "different msg")
    assert a == b


class _FakeStructuredInvoker:
    def __init__(self, result: object) -> None:
        self._result = result

    async def ainvoke(self, _messages: object) -> object:
        return self._result


class _FakeModel:
    def __init__(self, result: object) -> None:
        self._result = result

    def with_structured_output(self, _schema: object, method: str) -> _FakeStructuredInvoker:
        assert method == "function_calling"
        return _FakeStructuredInvoker(self._result)


@pytest.mark.asyncio
async def test_llm_selector_validates_output_and_locks_industry() -> None:
    payload = {
        "tenant": {
            "company_name": "Persona Co",
            "industry": "wrong_industry",
            "size_band": "50-200",
            "primary_region": "APAC",
            "locale": "en-PH",
            "timezone": "Asia/Manila",
        },
        "selected_queue_ids": [101],
        "selected_project_ids": [501],
        "selected_dashboard_ids": [701],
        "selected_kpi_ids": [1],
        "selected_request_type_ids": [801],
        "selected_employee_ids": [1],
        "employee_overrides": [
            {
                "id": 1,
                "position": "Director",
                "team": "Ops",
                "department": "Operations",
                "job_title": "Director",
                "job_type": "Full-Time",
                "job_level": "Director",
            }
        ],
    }
    selector = LLMSelector(model=_FakeModel(payload))  # type: ignore[arg-type]
    result = await selector.select_async(_view(), "We are in PH")
    assert result.tenant.company_name == "Persona Co"
    assert result.tenant.industry == "bpo_contact_center"


@pytest.mark.asyncio
async def test_llm_selector_falls_back_on_model_error() -> None:
    class _FailingInvoker:
        async def ainvoke(self, _messages: object) -> object:
            raise RuntimeError("boom")

    class _FailingModel:
        def with_structured_output(self, _schema: object, method: str) -> _FailingInvoker:
            assert method == "function_calling"
            return _FailingInvoker()

    selector = LLMSelector(
        model=_FailingModel(),  # type: ignore[arg-type]
        fallback_selector=BaselineSelector(),
    )
    result = await selector.select_async(_view(), "ignored")
    assert result.tenant.company_name == "Manifest Defaults Co"
    assert result.selected_queue_ids == [101, 102]
