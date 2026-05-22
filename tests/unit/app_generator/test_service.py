from __future__ import annotations

import pytest

from agents.app_generator.service import AppGeneratorService
from core.exceptions import InvalidPayloadError


class _FakeCatalog:
    def get(self, bundle_key: str):  # noqa: ANN001
        return None


class _FakeTemplateRepo:
    pass


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


def test_assemble_returns_v2_only_payload() -> None:
    svc = AppGeneratorService(template_repo=_FakeTemplateRepo(), catalog=_FakeCatalog())
    payload = svc.assemble(
        session_id="sess-abc123",
        bundle_key="hr_hub",
        display_name="HR Hub",
        manifest=_valid_manifest(),
        modules=["hr_hub"],
    )
    assert payload.schema_version == "2.0"
    assert payload.manifest["schema_version"] == "2.0"
    assert payload.modules == ["hr_hub"]


def test_assemble_rejects_invalid_manifest() -> None:
    svc = AppGeneratorService(template_repo=_FakeTemplateRepo(), catalog=_FakeCatalog())
    manifest = _valid_manifest()
    manifest["schema_version"] = "1.0"
    with pytest.raises(InvalidPayloadError):
        svc.assemble(
            session_id="sess-abc123",
            bundle_key="hr_hub",
            display_name="HR Hub",
            manifest=manifest,
        )
