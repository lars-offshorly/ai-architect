from __future__ import annotations

import pytest
from pydantic import ValidationError

from agents.preview_generator.schemas import (
    CatalogRef,
    EmployeeRecord,
    HrHubSection,
    AppPayloadV2,
    TicketQueuesSection,
)


def _valid_manifest_dict() -> dict:
    return {
        "schema_version": "2.0",
        "session_id": "sess-abc123",
        "generated_at": "2026-05-19T10:00:00Z",
        "tenant": {
            "company_name": "Acme Corp",
            "industry": "Technology",
            "size_band": "mid-sized",
            "primary_region": "us-east-1",
            "locale": "en-US",
            "timezone": "America/New_York",
        },
        "tickets": {"queues": [{"id": 1, "name": "Support Queue"}]},
        "projects": {"projects": [{"id": 2, "name": "Alpha Project"}]},
        "dashboard": {"dashboards": [{"id": 3, "name": "Main Dashboard"}]},
        "kpi": {"kpis": [{"id": 4, "name": "Resolution Rate"}]},
        "hr_hub": {
            "employees": [
                {
                    "id": 1,
                    "position": "Engineer",
                    "team": "Platform",
                    "department": "Engineering",
                    "job_title": "Software Engineer",
                    "job_type": "full-time",
                    "job_level": "mid",
                }
            ],
            "request_types": [{"id": 5, "name": "PTO Request"}],
        },
    }


def test_parses_valid_manifest_from_target_contract_sample() -> None:
    manifest = AppPayloadV2(**_valid_manifest_dict())
    assert manifest.schema_version == "2.0"
    assert manifest.session_id == "sess-abc123"
    assert manifest.tenant.company_name == "Acme Corp"


def test_rejects_schema_version_1_0() -> None:
    data = _valid_manifest_dict()
    data["schema_version"] = "1.0"
    with pytest.raises(ValidationError):
        AppPayloadV2(**data)


def test_rejects_schema_version_missing() -> None:
    data = _valid_manifest_dict()
    del data["schema_version"]
    with pytest.raises(ValidationError):
        AppPayloadV2(**data)


def test_rejects_missing_tenant() -> None:
    data = _valid_manifest_dict()
    del data["tenant"]
    with pytest.raises(ValidationError):
        AppPayloadV2(**data)


def test_rejects_missing_hr_hub() -> None:
    data = _valid_manifest_dict()
    del data["hr_hub"]
    with pytest.raises(ValidationError):
        AppPayloadV2(**data)


def test_rejects_missing_kpi() -> None:
    data = _valid_manifest_dict()
    del data["kpi"]
    with pytest.raises(ValidationError):
        AppPayloadV2(**data)


def test_rejects_negative_catalog_ref_id() -> None:
    with pytest.raises(ValidationError):
        CatalogRef(id=-1, name="bad")


def test_rejects_zero_catalog_ref_id() -> None:
    with pytest.raises(ValidationError):
        CatalogRef(id=0, name="bad")


def test_accepts_empty_queues_list() -> None:
    section = TicketQueuesSection(queues=[])
    assert section.queues == []


def test_accepts_empty_employees_list() -> None:
    section = HrHubSection(employees=[], request_types=[])
    assert section.employees == []


def test_employee_record_rejects_missing_job_title() -> None:
    with pytest.raises(ValidationError):
        EmployeeRecord(
            id=1,
            position="Engineer",
            team="Platform",
            department="Engineering",
            job_type="full-time",
            job_level="mid",
        )


def test_tenant_info_rejects_missing_industry() -> None:
    data = _valid_manifest_dict()
    del data["tenant"]["industry"]
    with pytest.raises(ValidationError):
        AppPayloadV2(**data)
