"""Cross-section consistency tests for v2 manifest output.

Verifies that every ID in the emitter output is a valid reference to an
entry in the raw fixture catalog, IDs are unique within each output section,
and the tenant industry maps to a known bundle.
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
        session_id="consistency-test",
        generated_at=_FIXED_TS,
    )
    return manifest, output


_FIXTURE_PATHS = sorted(_SAMPLES_DIR.glob("tenant_provisioning_*.jsonc"))
_IDS = [p.stem for p in _FIXTURE_PATHS]


@pytest.mark.parametrize("fixture_path", _FIXTURE_PATHS, ids=_IDS)
def test_output_ids_are_subset_of_catalog(fixture_path: pathlib.Path) -> None:
    """Every ID in each output section must exist in the corresponding catalog."""
    manifest, output = _emit(fixture_path)

    checks = [
        (output["tickets"]["queues"], manifest["tickets"]["queues"], "tickets.queues"),
        (output["projects"]["projects"], manifest["projects"]["projects"], "projects.projects"),
        (output["dashboard"]["dashboards"], manifest["dashboard"]["dashboards"], "dashboard.dashboards"),
        (output["kpi"]["kpis"], manifest["kpi"]["kpis"], "kpi.kpis"),
        (output["hr_hub"]["employees"], manifest["hr_hub"]["employees"], "hr_hub.employees"),
        (output["hr_hub"]["request_types"], manifest["hr_hub"]["request_types"], "hr_hub.request_types"),
    ]
    for output_items, catalog_items, label in checks:
        catalog_ids = {entry["id"] for entry in catalog_items}
        for item in output_items:
            assert item["id"] in catalog_ids, (
                f"{label}: output ID {item['id']} not found in catalog"
            )


@pytest.mark.parametrize("fixture_path", _FIXTURE_PATHS, ids=_IDS)
def test_no_duplicate_ids_within_output_sections(fixture_path: pathlib.Path) -> None:
    """IDs within each output section must be unique."""
    _, output = _emit(fixture_path)

    sections = [
        (output["tickets"]["queues"], "tickets.queues"),
        (output["projects"]["projects"], "projects.projects"),
        (output["dashboard"]["dashboards"], "dashboard.dashboards"),
        (output["kpi"]["kpis"], "kpi.kpis"),
        (output["hr_hub"]["employees"], "hr_hub.employees"),
        (output["hr_hub"]["request_types"], "hr_hub.request_types"),
    ]
    for items, label in sections:
        ids = [item["id"] for item in items]
        assert len(ids) == len(set(ids)), f"{label}: duplicate IDs found: {ids}"


@pytest.mark.parametrize("fixture_path", _FIXTURE_PATHS, ids=_IDS)
def test_industry_maps_to_valid_bundle(fixture_path: pathlib.Path) -> None:
    """tenant.industry in emitter output must have an entry in industry_bundle_map.json."""
    _, output = _emit(fixture_path)
    map_path = _SAMPLES_DIR / "industry_bundle_map.json"
    bundle_map = json.loads(map_path.read_text(encoding="utf-8"))
    industry = output["tenant"]["industry"]
    assert industry in bundle_map["mappings"], (
        f"industry '{industry}' has no entry in industry_bundle_map.json"
    )
    assert bundle_map["mappings"][industry].get("bundle_key"), (
        f"industry '{industry}' maps to an empty bundle_key"
    )


@pytest.mark.parametrize("fixture_path", _FIXTURE_PATHS, ids=_IDS)
def test_employee_catalog_data_preserved_without_overrides(fixture_path: pathlib.Path) -> None:
    """Employees in output match catalog entries when no overrides are applied."""
    manifest, output = _emit(fixture_path)
    catalog_by_id = {e["id"]: e for e in manifest["hr_hub"]["employees"]}
    for emp in output["hr_hub"]["employees"]:
        catalog = catalog_by_id[emp["id"]]
        for field in ("position", "team", "department", "job_title", "job_type", "job_level"):
            assert emp[field] == catalog[field], (
                f"employee {emp['id']}.{field}: output '{emp[field]}' "
                f"!= catalog '{catalog[field]}'"
            )
