"""Emitter/validator parity: emit_tenant_provisioning output must validate as
TenantProvisioningManifest for every fixture in new_json_samples/.
Three assertions per fixture:
1. model_validate() passes — extra="forbid" catches surplus fields; required-field
   validation catches omissions. This is the core parity proof.
2. Output top-level keys exactly match the 9 TenantProvisioningManifest fields.
3. Each emitted employee dict has exactly the 7 EmployeeRecord fields.
"""
from __future__ import annotations

import json
import pathlib
import re
from datetime import datetime, timezone
from typing import Any

import pytest

from agents.preview_generator.schemas import TenantProvisioningManifest
from agents.tenant_provisioning import (
    SelectionResult,
    TenantSelection,
    emit_tenant_provisioning,
)

_SAMPLES_DIR = pathlib.Path(__file__).resolve().parents[4] / "new_json_samples"
_EXPECTED_TOP_KEYS = frozenset({
    "schema_version", "session_id", "generated_at",
    "tenant", "tickets", "projects", "dashboard", "kpi", "hr_hub",
})
_EXPECTED_EMPLOYEE_KEYS = frozenset({
    "id", "position", "team", "department", "job_title", "job_type", "job_level",
})
_FIXED_TS = datetime(2026, 5, 21, 10, 0, 0, tzinfo=timezone.utc)


def _strip_comments(text: str) -> str:
    return re.sub(r"//[^\n]*", "", text)


def _load_fixture(path: pathlib.Path) -> dict[str, Any]:
    return json.loads(_strip_comments(path.read_text(encoding="utf-8")))


def _selection_from_manifest(manifest: dict[str, Any]) -> SelectionResult:
    """Build a minimal valid SelectionResult by picking the first ID from each section."""
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
        selected_queue_ids=[manifest["tickets"]["queues"][0]["id"]],
        selected_project_ids=[manifest["projects"]["projects"][0]["id"]],
        selected_dashboard_ids=[manifest["dashboard"]["dashboards"][0]["id"]],
        selected_kpi_ids=[manifest["kpi"]["kpis"][0]["id"]],
        selected_request_type_ids=[manifest["hr_hub"]["request_types"][0]["id"]],
        selected_employee_ids=[manifest["hr_hub"]["employees"][0]["id"]],
    )


_FIXTURE_PATHS = sorted(_SAMPLES_DIR.glob("tenant_provisioning_*.jsonc"))


@pytest.mark.parametrize(
    "fixture_path",
    _FIXTURE_PATHS,
    ids=[p.stem for p in _FIXTURE_PATHS],
)
def test_emitter_output_validates_as_manifest(fixture_path: pathlib.Path) -> None:
    """Core parity proof: model_validate() must pass on emitter output."""
    manifest = _load_fixture(fixture_path)
    output = emit_tenant_provisioning(
        manifest,
        _selection_from_manifest(manifest),
        session_id="parity-test",
        generated_at=_FIXED_TS,
    )
    validated = TenantProvisioningManifest.model_validate(output)
    assert validated.schema_version == "2.0"
    assert validated.tenant.industry == manifest["tenant"]["industry"]


@pytest.mark.parametrize(
    "fixture_path",
    _FIXTURE_PATHS,
    ids=[p.stem for p in _FIXTURE_PATHS],
)
def test_emitter_output_top_level_keys_match_schema(fixture_path: pathlib.Path) -> None:
    """Emitter produces exactly the 9 top-level keys — no extras, no omissions."""
    manifest = _load_fixture(fixture_path)
    output = emit_tenant_provisioning(
        manifest,
        _selection_from_manifest(manifest),
        session_id="parity-test",
        generated_at=_FIXED_TS,
    )
    assert set(output.keys()) == _EXPECTED_TOP_KEYS


@pytest.mark.parametrize(
    "fixture_path",
    _FIXTURE_PATHS,
    ids=[p.stem for p in _FIXTURE_PATHS],
)
def test_emitter_employee_fields_match_employee_record(fixture_path: pathlib.Path) -> None:
    """Each emitted employee has exactly the 7 EmployeeRecord fields."""
    manifest = _load_fixture(fixture_path)
    output = emit_tenant_provisioning(
        manifest,
        _selection_from_manifest(manifest),
        session_id="parity-test",
        generated_at=_FIXED_TS,
    )
    for emp in output["hr_hub"]["employees"]:
        assert set(emp.keys()) == _EXPECTED_EMPLOYEE_KEYS, (
            f"employee {emp.get('id')} has unexpected keys: "
            f"{set(emp.keys()) ^ _EXPECTED_EMPLOYEE_KEYS}"
        )
