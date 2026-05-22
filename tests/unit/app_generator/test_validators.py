from __future__ import annotations

import pytest

from agents.app_generator.validators import validate_manifest
from core.exceptions import InvalidPayloadError


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


def test_validate_manifest_passes_for_valid_payload() -> None:
    validate_manifest(_valid_manifest())


def test_validate_manifest_rejects_wrong_schema_version() -> None:
    data = _valid_manifest()
    data["schema_version"] = "1.0"
    with pytest.raises(InvalidPayloadError, match="schema_version"):
        validate_manifest(data)
