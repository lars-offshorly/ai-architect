from __future__ import annotations

import pytest

from agents.app_generator.validators import (
    validate_dummy_data_json,
    validate_generation_json,
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
