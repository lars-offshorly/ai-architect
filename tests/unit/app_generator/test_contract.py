from __future__ import annotations

from agents.app_generator.contract import AppPayloadContract


def _valid_manifest() -> dict[str, object]:
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


def test_v2_contract_returns_no_errors_for_valid_manifest() -> None:
    contract = AppPayloadContract(
        schema_version="2.0",
        session_id="sess-abc123",
        bundle_key="hr_hub",
        display_name="HR Hub",
        modules=["hr_hub"],
        manifest=_valid_manifest(),
    )
    assert contract.validate_contract() == []


def test_v2_contract_returns_errors_for_invalid_manifest() -> None:
    bad_manifest = _valid_manifest()
    bad_manifest["schema_version"] = "1.0"
    contract = AppPayloadContract(
        schema_version="2.0",
        session_id="sess-abc123",
        bundle_key="hr_hub",
        display_name="HR Hub",
        modules=["hr_hub"],
        manifest=bad_manifest,
    )
    errors = contract.validate_contract()
    assert errors and any("schema_version" in e for e in errors)
