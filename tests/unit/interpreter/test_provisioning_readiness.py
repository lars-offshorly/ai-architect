from __future__ import annotations

from agents.interpreter.provisioning_readiness import (
    ProvisioningReadiness,
    TenantField,
)
from domain.models.extraction_result import (
    ExtractionResult,
    PersonalizationSignals,
)
from domain.models.session import Session


def test_is_ready_when_industry_and_company_known() -> None:
    session = Session(
        session_id="s1",
        company_industry_claim="bpo_contact_center",
        preselected_bundle_key="ticketing",
        inferred_company_name="Nexora Connect",
        inferred_team_size=280,
        inferred_region="PH",
    )
    extracted = ExtractionResult(session_id="s1")
    result = ProvisioningReadiness.evaluate(session, extracted)
    assert result.is_ready is True
    assert result.missing_required == ()
    assert result.missing_optional == ()


def test_missing_company_name_blocks_readiness() -> None:
    session = Session(
        session_id="s1",
        company_industry_claim="bpo_contact_center",
        preselected_bundle_key="ticketing",
    )
    extracted = ExtractionResult(session_id="s1")
    result = ProvisioningReadiness.evaluate(session, extracted)
    assert result.is_ready is False
    assert TenantField.COMPANY_NAME in result.missing_required
    assert result.next_field_to_ask() == TenantField.COMPANY_NAME


def test_missing_industry_blocks_readiness() -> None:
    session = Session(session_id="s1", inferred_company_name="Acme Co.")
    extracted = ExtractionResult(session_id="s1")
    result = ProvisioningReadiness.evaluate(session, extracted)
    assert result.is_ready is False
    assert TenantField.INDUSTRY in result.missing_required


def test_company_name_from_extraction_signals() -> None:
    session = Session(
        session_id="s1",
        company_industry_claim="bpo_contact_center",
    )
    extracted = ExtractionResult(
        session_id="s1",
        personalization_signals=PersonalizationSignals(company_name="Acme Co."),
    )
    result = ProvisioningReadiness.evaluate(session, extracted)
    assert result.is_ready is True


def test_generic_selected_bundle_does_not_satisfy_industry() -> None:
    """``generic`` is the fallback bundle, not an identified industry.

    Regression: the readiness check used to treat selected_bundle_key="generic"
    as a known industry, so a first-turn fallback persisting that key would
    let the conversation skip all further clarification on turn 2+.
    """
    session = Session(
        session_id="s1",
        selected_bundle_key="generic",
        inferred_company_name="EquipT",
    )
    result = ProvisioningReadiness.evaluate(session, None)
    assert result.is_ready is False
    assert TenantField.INDUSTRY in result.missing_required


def test_optional_fields_reported_but_dont_block() -> None:
    session = Session(
        session_id="s1",
        company_industry_claim="construction_firm",
        inferred_company_name="BuildCo",
        # No team size, no region.
    )
    result = ProvisioningReadiness.evaluate(session, None)
    assert result.is_ready is True
    assert TenantField.SIZE_BAND in result.missing_optional
    assert TenantField.PRIMARY_REGION in result.missing_optional
