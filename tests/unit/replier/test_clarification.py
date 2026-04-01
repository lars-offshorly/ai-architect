from __future__ import annotations

from agents.replier.clarification import is_critical
from domain.enums.missing_field_type import MissingFieldType


def test_is_critical_for_primary_use_case() -> None:
    assert is_critical(MissingFieldType.PRIMARY_USE_CASE) is True


def test_is_critical_for_team_size() -> None:
    assert is_critical(MissingFieldType.TEAM_SIZE) is False
