from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from agents.tenant_provisioning import (
    EmployeeOverride,
    SelectionResult,
    TenantSelection,
    emit_tenant_provisioning,
)
from agents.tenant_provisioning.emitter import EmitterError


def _manifest() -> dict[str, Any]:
    return {
        "schema_version": "2.0",
        "tenant": {
            "company_name": "Demo Co",
            "industry": "bpo_contact_center",
            "size_band": "50-200",
            "primary_region": "APAC",
            "locale": "en-PH",
            "timezone": "Asia/Manila",
        },
        "tickets": {
            "queues": [
                {"id": 101, "name": "Customer Care"},
                {"id": 102, "name": "Billing"},
                {"id": 110, "name": "Escalation"},
            ]
        },
        "projects": {
            "projects": [
                {"id": 501, "name": "Project A"},
                {"id": 502, "name": "Project B"},
            ]
        },
        "dashboard": {
            "dashboards": [
                {"id": 701, "name": "Ops"},
                {"id": 702, "name": "QA"},
            ]
        },
        "kpi": {
            "kpis": [
                {"id": 1, "name": "ART"},
                {"id": 2, "name": "SLA"},
            ]
        },
        "hr_hub": {
            "employees": [
                {
                    "id": 1,
                    "position": "Director",
                    "team": "Ops",
                    "department": "Operations",
                    "job_title": "Director of Ops",
                    "job_type": "Full-Time",
                    "job_level": "Director",
                },
                {
                    "id": 5,
                    "position": "CSR",
                    "team": "Support",
                    "department": "Operations",
                    "job_title": "CSR",
                    "job_type": "Full-Time",
                    "job_level": "Staff",
                },
            ],
            "request_types": [
                {"id": 801, "name": "Leave"},
                {"id": 805, "name": "Equipment"},
            ],
        },
    }


def _tenant() -> TenantSelection:
    return TenantSelection(
        company_name="Acme Outsourcing",
        industry="bpo_contact_center",
        size_band="200-500",
        primary_region="APAC",
        locale="en-PH",
        timezone="Asia/Manila",
    )


def test_emit_full_selection_produces_expected_payload() -> None:
    selection = SelectionResult(
        tenant=_tenant(),
        selected_queue_ids=[102, 101],  # input order shouldn't matter
        selected_project_ids=[501],
        selected_dashboard_ids=[701, 702],
        selected_kpi_ids=[1, 2],
        selected_request_type_ids=[801],
        selected_employee_ids=[1, 5],
        employee_overrides=[
            EmployeeOverride(
                id=5,
                position="Senior CSR",
                team="Support",
                department="Operations",
                job_title="Senior CSR",
                job_type="Full-Time",
                job_level="Senior",
            ),
        ],
    )

    result = emit_tenant_provisioning(
        _manifest(),
        selection,
        session_id="sess-1",
        generated_at=datetime(2026, 5, 18, 12, 0, 0, tzinfo=timezone.utc),
    )

    assert result["schema_version"] == "2.0"
    assert result["session_id"] == "sess-1"
    assert result["generated_at"] == "2026-05-18T12:00:00Z"
    assert result["tenant"]["company_name"] == "Acme Outsourcing"

    # Output order follows manifest order, not selection order.
    assert [q["id"] for q in result["tickets"]["queues"]] == [101, 102]
    assert [p["id"] for p in result["projects"]["projects"]] == [501]
    assert [d["id"] for d in result["dashboard"]["dashboards"]] == [701, 702]
    assert [k["id"] for k in result["kpi"]["kpis"]] == [1, 2]
    assert [r["id"] for r in result["hr_hub"]["request_types"]] == [801]

    employees = result["hr_hub"]["employees"]
    assert [e["id"] for e in employees] == [1, 5]
    # Employee 1: no override, manifest defaults preserved.
    assert employees[0]["position"] == "Director"
    # Employee 5: override applied.
    assert employees[1]["position"] == "Senior CSR"
    assert employees[1]["job_level"] == "Senior"


def test_emit_empty_selections_are_valid() -> None:
    selection = SelectionResult(tenant=_tenant())
    result = emit_tenant_provisioning(
        _manifest(), selection, session_id="sess-2"
    )
    assert result["tickets"]["queues"] == []
    assert result["projects"]["projects"] == []
    assert result["dashboard"]["dashboards"] == []
    assert result["kpi"]["kpis"] == []
    assert result["hr_hub"]["request_types"] == []
    assert result["hr_hub"]["employees"] == []


def test_emit_rejects_industry_mismatch() -> None:
    tenant = _tenant().model_copy(update={"industry": "construction"})
    selection = SelectionResult(tenant=tenant)
    with pytest.raises(EmitterError, match="tenant.industry must equal"):
        emit_tenant_provisioning(
            _manifest(), selection, session_id="sess-3"
        )


def test_emit_rejects_unknown_queue_id() -> None:
    selection = SelectionResult(
        tenant=_tenant(),
        selected_queue_ids=[101, 999],
    )
    with pytest.raises(EmitterError, match="tickets.queues.*999"):
        emit_tenant_provisioning(
            _manifest(), selection, session_id="sess-4"
        )


def test_emit_rejects_unknown_employee_id() -> None:
    selection = SelectionResult(
        tenant=_tenant(),
        selected_employee_ids=[1, 999],
    )
    with pytest.raises(EmitterError, match="hr_hub.employees.*999"):
        emit_tenant_provisioning(
            _manifest(), selection, session_id="sess-5"
        )


def test_emit_does_not_mutate_manifest() -> None:
    manifest = _manifest()
    snapshot = {
        "queues": list(manifest["tickets"]["queues"]),
        "employees": list(manifest["hr_hub"]["employees"]),
    }
    selection = SelectionResult(
        tenant=_tenant(),
        selected_queue_ids=[101],
        selected_employee_ids=[1],
        employee_overrides=[
            EmployeeOverride(
                id=1,
                position="X",
                team="Y",
                department="Z",
                job_title="T",
                job_type="Full-Time",
                job_level="Director",
            ),
        ],
    )
    emit_tenant_provisioning(manifest, selection, session_id="sess-6")
    assert manifest["tickets"]["queues"] == snapshot["queues"]
    assert manifest["hr_hub"]["employees"] == snapshot["employees"]


def test_emit_is_deterministic_for_same_inputs() -> None:
    selection = SelectionResult(
        tenant=_tenant(),
        selected_queue_ids=[101, 102],
        selected_employee_ids=[1, 5],
    )
    ts = datetime(2026, 5, 18, 12, 0, 0, tzinfo=timezone.utc)
    a = emit_tenant_provisioning(
        _manifest(), selection, session_id="sess-X", generated_at=ts
    )
    b = emit_tenant_provisioning(
        _manifest(), selection, session_id="sess-X", generated_at=ts
    )
    assert a == b
