from __future__ import annotations

from agents.app_generator.contract import AppPayloadContract


def _valid_v1_contract_kwargs() -> dict:
    return {
        "schema_version": "1.0",
        "session_id": "sess-abc123",
        "bundle_key": "hr_hub",
        "display_name": "HR Hub",
        "modules": ["tickets", "dashboard"],
        "generation_json": {
            "schema_version": "1.0",
            "bundle_key": "hr_hub",
            "modules": ["tickets", "dashboard"],
            "config": {},
        },
        "dummy_data_json": {
            "bundle_key": "hr_hub",
            "stores": {"tickets": []},
        },
    }


def _valid_v2_manifest_dict() -> dict:
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


# ---------------------------------------------------------------------------
# v1 regression tests
# ---------------------------------------------------------------------------


def test_v1_contract_returns_no_errors_for_valid_payload() -> None:
    contract = AppPayloadContract(**_valid_v1_contract_kwargs())
    assert contract.validate_contract() == []


def test_v1_contract_returns_errors_for_missing_generation_key() -> None:
    kwargs = _valid_v1_contract_kwargs()
    del kwargs["generation_json"]["config"]
    contract = AppPayloadContract(**kwargs)
    errors = contract.validate_contract()
    assert len(errors) == 1
    assert "generation_json" in errors[0]


def test_v1_contract_returns_errors_for_empty_modules() -> None:
    kwargs = _valid_v1_contract_kwargs()
    kwargs["modules"] = []
    contract = AppPayloadContract(**kwargs)
    errors = contract.validate_contract()
    assert any("modules" in e for e in errors)


def test_v1_contract_returns_errors_for_missing_relationships() -> None:
    kwargs = _valid_v1_contract_kwargs()
    kwargs["has_entity_relationships"] = True
    # config exists but 'relationships' key is absent
    contract = AppPayloadContract(**kwargs)
    errors = contract.validate_contract()
    assert any("relationships" in e for e in errors)


# ---------------------------------------------------------------------------
# v2 contract tests
# ---------------------------------------------------------------------------


def test_v2_contract_returns_no_errors_for_valid_manifest() -> None:
    contract = AppPayloadContract(
        **_valid_v1_contract_kwargs(), v2_manifest=_valid_v2_manifest_dict()
    )
    assert contract.validate_contract() == []


def test_v2_contract_returns_errors_for_invalid_manifest() -> None:
    bad_manifest = _valid_v2_manifest_dict()
    bad_manifest["schema_version"] = "1.0"
    contract = AppPayloadContract(**_valid_v1_contract_kwargs(), v2_manifest=bad_manifest)
    errors = contract.validate_contract()
    assert errors and any("schema_version" in e for e in errors)


def test_v2_contract_ignores_v1_fields_when_v2_manifest_present() -> None:
    kwargs = _valid_v1_contract_kwargs()
    # Deliberately corrupt v1 fields — they should be ignored when v2_manifest is set
    kwargs["generation_json"] = {}
    kwargs["modules"] = []
    contract = AppPayloadContract(**kwargs, v2_manifest=_valid_v2_manifest_dict())
    assert contract.validate_contract() == []


def test_v1_path_used_when_v2_manifest_is_none() -> None:
    kwargs = _valid_v1_contract_kwargs()
    kwargs["modules"] = []
    contract = AppPayloadContract(**kwargs, v2_manifest=None)
    errors = contract.validate_contract()
    assert any("modules" in e for e in errors)
