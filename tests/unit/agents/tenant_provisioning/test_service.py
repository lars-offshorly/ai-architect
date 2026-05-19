from __future__ import annotations

from datetime import datetime, timezone

import pytest

from agents.tenant_provisioning import (
    CatalogView,
    SelectionResult,
    TenantProvisioningError,
    TenantProvisioningService,
    TenantSelection,
)
from domain.services.canonical_manifest_registry import CanonicalManifestRegistry
from domain.services.canonical_bundle_resolver import CanonicalBundleResolver
from domain.services.canonical_metadata_service import CanonicalMetadataService
from domain.services.canonical_payload_builder import CanonicalPayloadBuilder
from domain.services.registry_facade import RegistryFacade


@pytest.fixture
def facade() -> RegistryFacade:
    registry = CanonicalManifestRegistry("new_json_samples")
    registry.load_all()
    return RegistryFacade(
        resolver=CanonicalBundleResolver(registry=registry),
        payload_builder=CanonicalPayloadBuilder(registry=registry),
        metadata_service=CanonicalMetadataService(registry),
    )


def test_service_with_baseline_emits_full_manifest_for_known_bundle(
    facade: RegistryFacade,
) -> None:
    service = TenantProvisioningService.with_baseline(facade)
    result = service.provision(
        bundle_key="ticketing",
        user_message="we run a contact center",
        session_id="sess-bpo",
        generated_at=datetime(2026, 5, 18, 12, 0, 0, tzinfo=timezone.utc),
    )
    assert result["session_id"] == "sess-bpo"
    assert result["generated_at"] == "2026-05-18T12:00:00Z"
    assert result["tenant"]["industry"] == "bpo_contact_center"
    # Baseline selects all 6 queues + 3 projects + 3 dashboards from BPO catalog.
    assert len(result["tickets"]["queues"]) == 6
    assert len(result["projects"]["projects"]) == 3
    assert len(result["dashboard"]["dashboards"]) == 3
    assert len(result["kpi"]["kpis"]) == 13
    assert len(result["hr_hub"]["request_types"]) == 4
    assert len(result["hr_hub"]["employees"]) == 7


def test_service_raises_for_unknown_bundle(facade: RegistryFacade) -> None:
    service = TenantProvisioningService.with_baseline(facade)
    with pytest.raises(TenantProvisioningError, match="No canonical manifest"):
        service.provision(
            bundle_key="does_not_exist",
            user_message="",
            session_id="sess-x",
        )


def test_service_delegates_to_injected_selector(facade: RegistryFacade) -> None:
    captured: dict[str, object] = {}

    class StubSelector:
        def select(
            self, catalog_view: CatalogView, user_message: str
        ) -> SelectionResult:
            captured["industry"] = catalog_view.bundle_industry
            captured["message"] = user_message
            return SelectionResult(
                tenant=TenantSelection(
                    company_name="Stub Co",
                    industry=catalog_view.bundle_industry,
                    size_band="10-50",
                    primary_region="APAC",
                    locale="en-PH",
                    timezone="Asia/Manila",
                ),
                selected_queue_ids=[101],  # tiny subset
            )

    service = TenantProvisioningService(
        registry_facade=facade, selector=StubSelector()
    )
    result = service.provision(
        bundle_key="ticketing",
        user_message="bpo contact center",
        session_id="sess-stub",
        generated_at=datetime(2026, 5, 18, tzinfo=timezone.utc),
    )
    assert captured == {
        "industry": "bpo_contact_center",
        "message": "bpo contact center",
    }
    assert result["tenant"]["company_name"] == "Stub Co"
    assert len(result["tickets"]["queues"]) == 1
    assert result["tickets"]["queues"][0]["id"] == 101


def test_service_construction_bundle_round_trips(facade: RegistryFacade) -> None:
    service = TenantProvisioningService.with_baseline(facade)
    result = service.provision(
        bundle_key="construction",
        user_message="building company",
        session_id="sess-cons",
        generated_at=datetime(2026, 5, 18, tzinfo=timezone.utc),
    )
    assert result["tenant"]["industry"] == "construction_firm"
    assert len(result["projects"]["projects"]) > 0
    assert len(result["hr_hub"]["employees"]) > 0


def test_service_hr_management_bundle_round_trips(facade: RegistryFacade) -> None:
    service = TenantProvisioningService.with_baseline(facade)
    result = service.provision(
        bundle_key="hr_management",
        user_message="recruiting firm",
        session_id="sess-hr",
        generated_at=datetime(2026, 5, 18, tzinfo=timezone.utc),
    )
    assert result["tenant"]["industry"] == "hr_recruitment_agency"
    assert len(result["hr_hub"]["request_types"]) > 0
