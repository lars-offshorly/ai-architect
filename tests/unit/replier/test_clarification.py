from __future__ import annotations

from agents.replier.clarification import detect_missing_fields, is_critical
from domain.enums.missing_field_type import MissingFieldType
from domain.models.extracted_info import ExtractedInfo


def test_detect_missing_fields_all_empty() -> None:
    extracted = ExtractedInfo(session_id="test", slots={})
    required = ["primary_use_case", "team_size"]
    missing = detect_missing_fields(extracted, required)
    assert MissingFieldType.PRIMARY_USE_CASE in missing


def test_detect_missing_fields_all_present() -> None:
    extracted = ExtractedInfo(
        session_id="test",
        slots={"primary_use_case": "HR requests", "team_size": 20},
    )
    required = ["primary_use_case", "team_size"]
    missing = detect_missing_fields(extracted, required)
    assert missing == []


def test_detect_missing_fields_skips_unknown_slot() -> None:
    extracted = ExtractedInfo(session_id="test", slots={})
    required = ["nonexistent_slot"]
    missing = detect_missing_fields(extracted, required)
    assert missing == []


def test_is_critical_for_primary_use_case() -> None:
    assert is_critical(MissingFieldType.PRIMARY_USE_CASE) is True


def test_is_critical_for_team_size() -> None:
    assert is_critical(MissingFieldType.TEAM_SIZE) is False
