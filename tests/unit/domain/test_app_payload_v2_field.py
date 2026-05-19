from __future__ import annotations

import pytest
from pydantic import ValidationError

from domain.models.app_payload import AppPayload


def _base_kwargs() -> dict[str, str]:
    return {
        "session_id": "sess-001",
        "bundle_key": "hr_hub",
        "display_name": "HR Hub",
    }


def test_v2_manifest_defaults_to_none() -> None:
    payload = AppPayload(**_base_kwargs())
    assert payload.v2_manifest is None


def test_v2_manifest_accepts_valid_dict() -> None:
    manifest = {"schema_version": "2.0", "key": "value"}
    payload = AppPayload(**_base_kwargs(), v2_manifest=manifest)
    assert payload.v2_manifest == manifest


def test_v2_manifest_serializes_in_model_dump() -> None:
    manifest = {"schema_version": "2.0"}
    payload = AppPayload(**_base_kwargs(), v2_manifest=manifest)
    dumped = payload.model_dump()
    assert "v2_manifest" in dumped
    assert dumped["v2_manifest"] == manifest


def test_model_dump_without_v2_manifest_has_none() -> None:
    payload = AppPayload(**_base_kwargs())
    assert payload.model_dump()["v2_manifest"] is None


def test_v2_manifest_rejects_non_dict() -> None:
    with pytest.raises(ValidationError):
        AppPayload(**_base_kwargs(), v2_manifest="not-a-dict")  # type: ignore[arg-type]
