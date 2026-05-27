from __future__ import annotations

# pylint: disable=duplicate-code,protected-access
import pytest

from agents.interpreter.provisioning_readiness import (
    ProvisioningReadinessResult,
    TenantField,
)
from agents.replier.clarification import build_bundle_variant_question
from agents.replier.service import ReplierService
from catalog.bundle_catalog import BundleVariantDefinition
from domain.enums.missing_field_type import MissingFieldType
from domain.models.extraction_result import ExtractionResult


@pytest.mark.asyncio
async def test_build_clarification_uses_extraction_missing_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = object.__new__(ReplierService)
    service._model = object()
    service._catalog = None

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
    service._catalog = None

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


@pytest.mark.asyncio
async def test_build_clarification_asks_about_tenant_field_when_no_missing_field() -> None:
    """When extraction has no MissingFieldType but readiness flags a missing
    required tenant field, return a deterministic question rather than an
    empty string. Regression: empty assistant reply rendered as nothing in UI.
    """
    service = object.__new__(ReplierService)
    service._model = object()
    service._catalog = None

    extracted = ExtractionResult(session_id="s1", missing_fields=[])
    readiness = ProvisioningReadinessResult(
        is_ready=False,
        missing_required=(TenantField.INDUSTRY,),
        missing_optional=(),
    )

    field, question = await service.build_clarification(
        session_id="s1",
        extracted=extracted,
        bundle_key="generic",
        readiness=readiness,
    )

    assert field is None
    assert question
    assert "business" in question.lower() or "industry" in question.lower()


def test_build_bundle_variant_question_lists_variants() -> None:
    question = build_bundle_variant_question(
        "ticketing",
        [
            BundleVariantDefinition(
                key="app-01",
                display_name="IT Helpdesk",
                description="",
                clarification_label="IT helpdesk",
            ),
            BundleVariantDefinition(
                key="app-02",
                display_name="Customer Support",
                description="",
                clarification_label="Customer support",
            ),
            BundleVariantDefinition(
                key="app-03",
                display_name="Facilities",
                description="",
                clarification_label="Facilities",
            ),
        ],
    )

    assert "IT helpdesk" in question
    assert "Customer support" in question
    assert "Facilities" in question
