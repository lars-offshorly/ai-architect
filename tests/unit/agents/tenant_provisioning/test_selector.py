from __future__ import annotations

from agents.tenant_provisioning import BaselineSelector, CatalogView
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
