from __future__ import annotations

import pytest

from domain.models.extracted_info import ExtractedInfo


def test_extracted_info_defaults() -> None:
    info = ExtractedInfo(session_id="test-session")
    assert info.company_name is None
    assert info.employee_names == []
    assert info.role_names == []
    assert info.slots == {}


def test_extracted_info_with_values() -> None:
    info = ExtractedInfo(
        session_id="test-session",
        company_name="Acme Corp",
        industry_hint="healthcare",
        employee_names=["Jane Smith", "Bob Chen"],
        role_names=["HR Manager"],
        slots={"team_size": 50},
    )
    assert info.company_name == "Acme Corp"
    assert info.industry_hint == "healthcare"
    assert len(info.employee_names) == 2
    assert info.slots["team_size"] == 50
