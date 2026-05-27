"""Regression tests for tenant override flow in PreviewFlow.

The user's case: they said "construction company named Equip ... PH ... 5
employees" but the previous preview JSON came back with the manifest's frozen
default tenant (e.g. 'Offshorly Construction'). This was because:

1. The BaselineSelector ignores user_message entirely.
2. The sync LLMSelector.select() falls back to baseline.
3. PreviewFlow._build_manifest never derived per-call overrides.

These tests pin the new behavior: PreviewFlow derives tenant overrides from
extraction signals + conversation history and passes them to the provisioning
service, which applies them to the SelectionResult before emit.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from domain.models.extraction_result import (
    ExtractionResult,
    PersonalizationSignals,
)
from orchestrators.preview_flow import (
    PreviewFlow,
    _derive_tenant_overrides,
)


def test_derive_company_name_from_extraction_signals() -> None:
    extracted = ExtractionResult(
        session_id="s1",
        personalization_signals=PersonalizationSignals(company_name="Equip"),
    )
    overrides = _derive_tenant_overrides(
        extraction_result=extracted,
        conversation_history=[
            {"role": "user", "content": "set up tickets for my construction firm"}
        ],
    )
    assert overrides["company_name"] == "Equip"


def test_derive_company_name_from_history_when_no_extraction() -> None:
    overrides = _derive_tenant_overrides(
        extraction_result=None,
        conversation_history=[
            {
                "role": "user",
                "content": (
                    "Im from PH and I have construction company named Equip. "
                    "I need a ticketing website for 5 employees please"
                ),
            }
        ],
    )
    assert overrides["company_name"] == "Equip"


def test_derive_size_band_from_employee_count() -> None:
    overrides = _derive_tenant_overrides(
        extraction_result=None,
        conversation_history=[
            {"role": "user", "content": "we have 5 employees"}
        ],
    )
    assert overrides["size_band"] == "1-10"


def test_derive_size_band_for_larger_team() -> None:
    overrides = _derive_tenant_overrides(
        extraction_result=None,
        conversation_history=[
            {"role": "user", "content": "we need QA dashboards for 280 employees"}
        ],
    )
    assert overrides["size_band"] == "200-500"


def test_derive_region_locale_timezone_from_ph_keywords() -> None:
    overrides = _derive_tenant_overrides(
        extraction_result=None,
        conversation_history=[
            {"role": "user", "content": "Im from PH and need a workspace"}
        ],
    )
    assert overrides["primary_region"] == "APAC"
    assert overrides["locale"] == "en-PH"
    assert overrides["timezone"] == "Asia/Manila"


def test_derive_returns_empty_when_nothing_to_infer() -> None:
    overrides = _derive_tenant_overrides(
        extraction_result=None,
        conversation_history=[
            {"role": "user", "content": "hi"}
        ],
    )
    assert overrides == {}


def test_preview_flow_passes_overrides_to_provisioning_service() -> None:
    """Full end-to-end: extraction + history → provision() receives overrides."""
    svc = MagicMock()
    svc.provision.return_value = {
        "schema_version": "2.0",
        "session_id": "s1",
        "generated_at": "2026-05-26T00:00:00Z",
        "tenant": {
            "company_name": "Equip",
            "industry": "construction_firm",
            "size_band": "1-10",
            "primary_region": "APAC",
            "locale": "en-PH",
            "timezone": "Asia/Manila",
        },
        "tickets": {"queues": []},
        "projects": {"projects": []},
        "dashboard": {"dashboards": []},
        "kpi": {"kpis": []},
        "hr_hub": {"employees": [], "request_types": []},
    }
    preview_service = SimpleNamespace(
        generate=lambda **kwargs: (["Projects"], None)
    )
    flow = PreviewFlow(
        preview_generator_service=preview_service,
        bundle_display_names={"construction": "Construction"},
        tenant_provisioning_service=svc,
    )

    flow.run(
        session_id="s1",
        bundle_key="construction",
        conversation_history=[
            {
                "role": "user",
                "content": (
                    "Im from PH and I have construction company named Equip. "
                    "I need a ticketing website for 5 employees please"
                ),
            }
        ],
        extraction_result=ExtractionResult(
            session_id="s1",
            personalization_signals=PersonalizationSignals(company_name="Equip"),
        ),
    )

    svc.provision.assert_called_once()
    kwargs = svc.provision.call_args.kwargs
    assert kwargs["tenant_overrides"]["company_name"] == "Equip"
    assert kwargs["tenant_overrides"]["size_band"] == "1-10"
    assert kwargs["tenant_overrides"]["primary_region"] == "APAC"
