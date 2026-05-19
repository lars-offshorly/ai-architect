from __future__ import annotations

import pytest

from agents.app_generator.validators import (
    validate_dummy_data_json,
    validate_generation_json,
    validate_v2_manifest,
)
from core.exceptions import InvalidPayloadError


def _valid_generation_json(bundle_key: str = "hr_hub") -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "bundle_key": bundle_key,
        "modules": ["tickets", "dashboard"],
        "config": {"ticket_statuses": ["pending", "resolved"]},
    }


def _valid_dummy_data_json(bundle_key: str = "hr_hub") -> dict[str, object]:
    return {
        "bundle_key": bundle_key,
        "stores": {"tickets": []},
    }


def test_validate_generation_json_passes() -> None:
    validate_generation_json(_valid_generation_json(), "hr_hub")


def test_validate_generation_json_missing_key_raises() -> None:
    data = _valid_generation_json()
    del data["config"]
    with pytest.raises(InvalidPayloadError):
        validate_generation_json(data, "hr_hub")


def test_validate_generation_json_bundle_mismatch_raises() -> None:
    with pytest.raises(InvalidPayloadError):
        validate_generation_json(_valid_generation_json("hr_hub"), "project_ops")


def test_validate_generation_json_empty_modules_raises() -> None:
    data = _valid_generation_json()
    data["modules"] = []
    with pytest.raises(InvalidPayloadError):
        validate_generation_json(data, "hr_hub")


def test_validate_dummy_data_json_passes() -> None:
    validate_dummy_data_json(_valid_dummy_data_json(), "hr_hub")


def test_validate_dummy_data_json_missing_stores_raises() -> None:
    data: dict[str, object] = {"bundle_key": "hr_hub"}
    with pytest.raises(InvalidPayloadError):
        validate_dummy_data_json(data, "hr_hub")


def test_validate_dummy_data_json_bundle_mismatch_raises() -> None:
    with pytest.raises(InvalidPayloadError):
        validate_dummy_data_json(_valid_dummy_data_json("hr_hub"), "project_mgmt")


# ---------------------------------------------------------------------------
# validate_v2_manifest
# ---------------------------------------------------------------------------


def _valid_v2_manifest() -> dict[str, object]:
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
        "tickets": {"queues": []},
        "projects": {"projects": []},
        "dashboard": {"dashboards": []},
        "kpi": {"kpis": []},
        "hr_hub": {"employees": [], "request_types": []},
    }


def test_validate_v2_manifest_passes_for_valid_payload() -> None:
    validate_v2_manifest(_valid_v2_manifest())


def test_validate_v2_manifest_rejects_wrong_schema_version() -> None:
    data = _valid_v2_manifest()
    data["schema_version"] = "1.0"
    with pytest.raises(InvalidPayloadError, match="schema_version"):
        validate_v2_manifest(data)


def test_validate_v2_manifest_rejects_missing_top_level_key() -> None:
    data = _valid_v2_manifest()
    del data["projects"]
    with pytest.raises(InvalidPayloadError, match="projects"):
        validate_v2_manifest(data)


def test_validate_v2_manifest_rejects_malformed_tenant() -> None:
    data = _valid_v2_manifest()
    data["tenant"] = {"company_name": "Acme Corp"}  # missing 5 fields
    with pytest.raises(InvalidPayloadError, match="tenant"):
        validate_v2_manifest(data)


def test_validate_v2_manifest_rejects_tenant_as_non_dict() -> None:
    data = _valid_v2_manifest()
    data["tenant"] = "not-a-dict"
    with pytest.raises(InvalidPayloadError, match="tenant"):
        validate_v2_manifest(data)


def test_validate_v2_manifest_rejects_missing_hr_hub_employees() -> None:
    data = _valid_v2_manifest()
    data["hr_hub"] = {"request_types": []}
    with pytest.raises(InvalidPayloadError, match="hr_hub"):
        validate_v2_manifest(data)


def test_validate_v2_manifest_accepts_empty_queues() -> None:
    data = _valid_v2_manifest()
    data["tickets"] = {"queues": []}
    validate_v2_manifest(data)  # must not raise


def test_validate_v2_manifest_rejects_negative_catalog_ref_id() -> None:
    data = _valid_v2_manifest()
    data["tickets"] = {"queues": [{"id": -1, "name": "bad"}]}
    with pytest.raises(InvalidPayloadError):
        validate_v2_manifest(data)
