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


def test_manifest_is_required() -> None:
    with pytest.raises(ValidationError):
        AppPayload(**_base_kwargs())


def test_manifest_accepts_valid_dict() -> None:
    manifest = {"schema_version": "2.0", "key": "value"}
    payload = AppPayload(**_base_kwargs(), manifest=manifest)
    assert payload.manifest == manifest


def test_manifest_serializes_in_model_dump() -> None:
    manifest = {"schema_version": "2.0"}
    payload = AppPayload(**_base_kwargs(), manifest=manifest)
    dumped = payload.model_dump()
    assert "manifest" in dumped
    assert dumped["manifest"] == manifest


def test_manifest_rejects_non_dict() -> None:
    with pytest.raises(ValidationError):
        AppPayload(**_base_kwargs(), manifest="not-a-dict")  # type: ignore[arg-type]
