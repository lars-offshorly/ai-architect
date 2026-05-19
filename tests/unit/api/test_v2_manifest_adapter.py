from __future__ import annotations

import pytest

from api.adapters.v2_manifest_adapter import build_v2_manifest
from domain.models.extraction_result import ExtractionResult, PersonalizationSignals
from domain.models.session import Session


@pytest.mark.asyncio
async def test_build_v2_manifest_uses_ph_context_and_self_name_fallback() -> None:
    session = Session(
        session_id="sess-ph",
        accumulated_extraction=ExtractionResult(session_id="sess-ph"),
    )

    manifest = await build_v2_manifest(
        session=session,
        dummy_data_json={"stores": {}},
        bundle_key="bpo_contact_center",
        display_name=None,
        conversation_history=[
            {"role": "user", "content": "Hi, my name is christian and I am from PH."}
        ],
    )

    assert manifest["tenant"]["company_name"] == "Christian's Workspace"
    assert manifest["tenant"]["primary_region"] == "APAC"
    assert manifest["tenant"]["locale"] == "en-PH"
    assert manifest["tenant"]["timezone"] == "Asia/Manila"


@pytest.mark.asyncio
async def test_build_v2_manifest_prefers_extracted_company_name() -> None:
    extraction = ExtractionResult(
        session_id="sess-company",
        personalization_signals=PersonalizationSignals(company_name="Vertex Solutions"),
    )
    session = Session(session_id="sess-company", accumulated_extraction=extraction)

    manifest = await build_v2_manifest(
        session=session,
        dummy_data_json={"stores": {}},
        bundle_key="bpo_contact_center",
        display_name=None,
        conversation_history=[
            {"role": "user", "content": "my name is christian and I am from PH"}
        ],
    )

    assert manifest["tenant"]["company_name"] == "Vertex Solutions"
