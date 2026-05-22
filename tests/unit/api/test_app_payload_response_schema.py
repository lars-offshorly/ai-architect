from __future__ import annotations

from api.schemas.app_payload import AppPayloadResponseSchema


def _base_kwargs() -> dict:
    return {
        "schema_version": "2.0",
        "session_id": "sess-abc",
        "bundle_key": "ticketing",
        "display_name": "Ticketing",
        "modules": ["tickets"],
        "manifest": {"schema_version": "2.0", "session_id": "sess-abc"},
    }


def test_manifest_accepts_valid_dict() -> None:
    manifest = {"schema_version": "2.0", "session_id": "sess-abc"}
    kwargs = _base_kwargs()
    kwargs["manifest"] = manifest
    schema = AppPayloadResponseSchema(**kwargs)
    assert schema.manifest == manifest


def test_manifest_serializes_in_model_dump() -> None:
    manifest = {"schema_version": "2.0"}
    kwargs = _base_kwargs()
    kwargs["manifest"] = manifest
    schema = AppPayloadResponseSchema(**kwargs)
    dumped = schema.model_dump()
    assert "manifest" in dumped
    assert dumped["manifest"] == manifest


def test_manifest_is_required() -> None:
    kwargs = _base_kwargs()
    kwargs.pop("manifest")
    from pydantic import ValidationError

    try:
        AppPayloadResponseSchema(**kwargs)
        assert False, "expected validation error"
    except ValidationError:
        assert True


def test_preview_type_still_supported() -> None:
    schema = AppPayloadResponseSchema(**_base_kwargs(), preview_type="confirmed")
    assert schema.preview_type == "confirmed"
    assert schema.manifest["schema_version"] == "2.0"
