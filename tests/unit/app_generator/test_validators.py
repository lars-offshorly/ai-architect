from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.app_generator.validators import (
    validate_dummy_data_json,
    validate_generation_json,
)
from core.exceptions import InvalidPayloadError

_BUNDLES_DIR = Path("src/templates/bundles")


def _load_generation_json(bundle: str = "hr_hub") -> dict[str, object]:
    return json.loads((_BUNDLES_DIR / bundle / "app.json").read_text())


def _load_dummy_data_json(bundle: str = "hr_hub") -> dict[str, object]:
    raw = json.loads((_BUNDLES_DIR / bundle / "dummy_data.json").read_text())
    raw.setdefault("schema_version", "1.0")
    raw.setdefault("session_id", "test-session-000")
    return raw


def test_validate_generation_json_passes() -> None:
    validate_generation_json(_load_generation_json(), "hr_hub")


def test_validate_generation_json_missing_key_raises() -> None:
    data = _load_generation_json()
    del data["config"]
    with pytest.raises(InvalidPayloadError):
        validate_generation_json(data, "hr_hub")


def test_validate_generation_json_bundle_mismatch_raises() -> None:
    with pytest.raises(InvalidPayloadError):
        validate_generation_json(_load_generation_json("hr_hub"), "project_ops")


def test_validate_generation_json_empty_modules_raises() -> None:
    data = _load_generation_json()
    data["modules"] = []
    with pytest.raises(InvalidPayloadError):
        validate_generation_json(data, "hr_hub")


def test_validate_dummy_data_json_passes() -> None:
    validate_dummy_data_json(_load_dummy_data_json(), "hr_hub")


def test_validate_dummy_data_json_missing_stores_raises() -> None:
    data = _load_dummy_data_json()
    del data["stores"]
    with pytest.raises(InvalidPayloadError):
        validate_dummy_data_json(data, "hr_hub")
