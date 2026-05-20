from __future__ import annotations

from api.schemas.app_payload import AppPayloadResponseSchema


def _base_kwargs() -> dict:
    return {
        "schema_version": "1.0",
        "session_id": "sess-abc",
        "bundle_key": "ticketing",
        "display_name": "Ticketing",
        "modules": ["tickets"],
        "generation_json": {},
        "dummy_data_json": {},
    }


def test_v2_manifest_defaults_to_none() -> None:
    schema = AppPayloadResponseSchema(**_base_kwargs())
    assert schema.v2_manifest is None


def test_v2_manifest_accepts_valid_dict() -> None:
    manifest = {"schema_version": "2.0", "session_id": "sess-abc"}
    schema = AppPayloadResponseSchema(**_base_kwargs(), v2_manifest=manifest)
    assert schema.v2_manifest == manifest


def test_v2_manifest_serializes_in_model_dump() -> None:
    manifest = {"schema_version": "2.0"}
    schema = AppPayloadResponseSchema(**_base_kwargs(), v2_manifest=manifest)
    dumped = schema.model_dump()
    assert "v2_manifest" in dumped
    assert dumped["v2_manifest"] == manifest


def test_v2_manifest_is_none_in_model_dump_when_absent() -> None:
    schema = AppPayloadResponseSchema(**_base_kwargs())
    assert schema.model_dump()["v2_manifest"] is None


def test_existing_fields_unaffected_by_v2_manifest_addition() -> None:
    schema = AppPayloadResponseSchema(**_base_kwargs(), preview_type="confirmed")
    assert schema.preview_type == "confirmed"
    assert schema.v2_manifest is None
