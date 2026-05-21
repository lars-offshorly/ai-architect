"""Section-level integration tests for v2 manifest emitter output.

Selects every catalog ID in each section so the emitter output mirrors the
full catalog. Each test function validates one section independently against
both the raw fixture data (source of truth) and the structural constraints
from TenantProvisioningManifest sub-models.
"""
from __future__ import annotations

import json
import pathlib
import re
from datetime import datetime, timezone
from typing import Any

import pytest

from agents.tenant_provisioning import (
    SelectionResult,
    TenantSelection,
    emit_tenant_provisioning,
)

_SAMPLES_DIR = pathlib.Path(__file__).resolve().parents[2] / "new_json_samples"
_FIXED_TS = datetime(2026, 5, 21, 10, 0, 0, tzinfo=timezone.utc)


def _strip_comments(text: str) -> str:
    return re.sub(r"//[^\n]*", "", text)


def _load_fixture(path: pathlib.Path) -> dict[str, Any]:
    return json.loads(_strip_comments(path.read_text(encoding="utf-8")))


def _full_selection(manifest: dict[str, Any]) -> SelectionResult:
    """Select every available ID from every catalog section."""
    t = manifest["tenant"]
    return SelectionResult(
        tenant=TenantSelection(
            company_name=t["company_name"],
            industry=t["industry"],
            size_band=t["size_band"],
            primary_region=t["primary_region"],
            locale=t["locale"],
            timezone=t["timezone"],
        ),
        selected_queue_ids=[q["id"] for q in manifest["tickets"]["queues"]],
        selected_project_ids=[p["id"] for p in manifest["projects"]["projects"]],
        selected_dashboard_ids=[d["id"] for d in manifest["dashboard"]["dashboards"]],
        selected_kpi_ids=[k["id"] for k in manifest["kpi"]["kpis"]],
        selected_request_type_ids=[r["id"] for r in manifest["hr_hub"]["request_types"]],
        selected_employee_ids=[e["id"] for e in manifest["hr_hub"]["employees"]],
    )


def _emit(fixture_path: pathlib.Path) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = _load_fixture(fixture_path)
    output = emit_tenant_provisioning(
        manifest,
        _full_selection(manifest),
        session_id="section-test",
        generated_at=_FIXED_TS,
    )
    return manifest, output


_FIXTURE_PATHS = sorted(_SAMPLES_DIR.glob("tenant_provisioning_*.jsonc"))
_IDS = [p.stem for p in _FIXTURE_PATHS]


@pytest.mark.parametrize("fixture_path", _FIXTURE_PATHS, ids=_IDS)
def test_tenant_section(fixture_path: pathlib.Path) -> None:
    manifest, output = _emit(fixture_path)
    tenant = output["tenant"]
    for field in ("company_name", "industry", "size_band", "primary_region", "locale", "timezone"):
        assert field in tenant, f"tenant missing field: {field}"
        assert isinstance(tenant[field], str) and tenant[field], (
            f"tenant.{field} must be a non-empty string"
        )
    assert tenant["industry"] == manifest["tenant"]["industry"]


@pytest.mark.parametrize("fixture_path", _FIXTURE_PATHS, ids=_IDS)
def test_tickets_section(fixture_path: pathlib.Path) -> None:
    manifest, output = _emit(fixture_path)
    catalog_ids = [q["id"] for q in manifest["tickets"]["queues"]]
    output_queues = output["tickets"]["queues"]
    assert [q["id"] for q in output_queues] == catalog_ids
    for q in output_queues:
        assert isinstance(q["id"], int) and q["id"] > 0
        assert isinstance(q["name"], str) and q["name"]


@pytest.mark.parametrize("fixture_path", _FIXTURE_PATHS, ids=_IDS)
def test_projects_section(fixture_path: pathlib.Path) -> None:
    manifest, output = _emit(fixture_path)
    catalog_ids = [p["id"] for p in manifest["projects"]["projects"]]
    output_projects = output["projects"]["projects"]
    assert [p["id"] for p in output_projects] == catalog_ids
    for p in output_projects:
        assert isinstance(p["id"], int) and p["id"] > 0
        assert isinstance(p["name"], str) and p["name"]


@pytest.mark.parametrize("fixture_path", _FIXTURE_PATHS, ids=_IDS)
def test_dashboard_section(fixture_path: pathlib.Path) -> None:
    manifest, output = _emit(fixture_path)
    catalog_ids = [d["id"] for d in manifest["dashboard"]["dashboards"]]
    output_dashboards = output["dashboard"]["dashboards"]
    assert [d["id"] for d in output_dashboards] == catalog_ids
    for d in output_dashboards:
        assert isinstance(d["id"], int) and d["id"] > 0
        assert isinstance(d["name"], str) and d["name"]


@pytest.mark.parametrize("fixture_path", _FIXTURE_PATHS, ids=_IDS)
def test_kpi_section(fixture_path: pathlib.Path) -> None:
    manifest, output = _emit(fixture_path)
    catalog_ids = [k["id"] for k in manifest["kpi"]["kpis"]]
    output_kpis = output["kpi"]["kpis"]
    assert [k["id"] for k in output_kpis] == catalog_ids
    for k in output_kpis:
        assert isinstance(k["id"], int) and k["id"] > 0
        assert isinstance(k["name"], str) and k["name"]


@pytest.mark.parametrize("fixture_path", _FIXTURE_PATHS, ids=_IDS)
def test_hr_hub_section(fixture_path: pathlib.Path) -> None:
    manifest, output = _emit(fixture_path)
    catalog_emp_ids = [e["id"] for e in manifest["hr_hub"]["employees"]]
    catalog_rt_ids = [r["id"] for r in manifest["hr_hub"]["request_types"]]
    output_employees = output["hr_hub"]["employees"]
    output_request_types = output["hr_hub"]["request_types"]

    assert [e["id"] for e in output_employees] == catalog_emp_ids
    assert [r["id"] for r in output_request_types] == catalog_rt_ids

    for emp in output_employees:
        for field in ("id", "position", "team", "department", "job_title", "job_type", "job_level"):
            assert field in emp, f"employee missing field: {field}"
        assert isinstance(emp["id"], int) and emp["id"] > 0
        for field in ("position", "team", "department", "job_title", "job_type", "job_level"):
            assert isinstance(emp[field], str) and emp[field], (
                f"employee.{field} must be non-empty"
            )
    for r in output_request_types:
        assert isinstance(r["id"], int) and r["id"] > 0
        assert isinstance(r["name"], str) and r["name"]
