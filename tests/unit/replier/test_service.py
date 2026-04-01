from __future__ import annotations

# pylint: disable=duplicate-code,protected-access
import pytest

from agents.replier.service import ReplierService
from domain.enums.missing_field_type import MissingFieldType
from domain.models.extraction_result import ExtractionResult


@pytest.mark.asyncio
async def test_build_clarification_uses_extraction_missing_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = object.__new__(ReplierService)
    service._model = object()

    async def fake_generate(*_args: object, **_kwargs: object) -> str:
        return "What is your use case?"

    monkeypatch.setattr(
        "agents.replier.service.generate_clarification_question", fake_generate
    )

    extracted = ExtractionResult(
        session_id="s1",
        missing_fields=[MissingFieldType.PRIMARY_USE_CASE],
    )
    field, question = await service.build_clarification(
        session_id="s1",
        extracted=extracted,
        bundle_key="hr_management",
    )

    assert field == MissingFieldType.PRIMARY_USE_CASE
    assert question == "What is your use case?"


@pytest.mark.asyncio
async def test_build_clarification_prioritizes_critical_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = object.__new__(ReplierService)
    service._model = object()

    async def fake_generate(*_args: object, **_kwargs: object) -> str:
        return "Please provide entity type."

    monkeypatch.setattr(
        "agents.replier.service.generate_clarification_question", fake_generate
    )

    extracted = ExtractionResult(
        session_id="s1",
        missing_fields=[MissingFieldType.COMPANY_NAME, MissingFieldType.ENTITY_TYPE],
    )
    field, _ = await service.build_clarification(
        session_id="s1",
        extracted=extracted,
        bundle_key="hr_management",
    )

    assert field == MissingFieldType.ENTITY_TYPE
