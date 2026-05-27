from __future__ import annotations

from pathlib import Path

import pytest

from domain.services.canonical_bundle_resolver import CanonicalBundleResolver
from domain.services.canonical_manifest_registry import (
    CanonicalManifestRegistry,
)
from domain.services.canonical_validation import (
    CanonicalValidationError,
    EmployeeMutableFieldsSpec,
    ReferentialIntegritySpec,
    UniqueIdsSpec,
    ValidationChain,
)
from domain.services.canonical_payload_builder import CanonicalPayloadBuilder


def _registry() -> CanonicalManifestRegistry:
    root = Path(__file__).resolve().parents[3]
    return CanonicalManifestRegistry(root / "new_json_samples")


def test_resolver_known_industry_maps_to_bundle() -> None:
    resolver = CanonicalBundleResolver(_registry(), strict_mapping=True)

    result = resolver.resolve("s1", "We run a BPO contact center")

    assert result.selected_bundle is not None
    assert result.selected_bundle.bundle_key == "ticketing"


def test_resolver_unknown_industry_returns_none_when_not_strict() -> None:
    resolver = CanonicalBundleResolver(_registry(), strict_mapping=False)

    result = resolver.resolve("s1", "We are a space robotics startup")

    # Resolver now defers to upstream (interpreter LLM stage) on miss
    # instead of inlining a generic fallback.
    assert result is None


def test_mapping_file_is_loaded() -> None:
    mapping = _registry().industry_bundle_map()
    assert mapping["construction_firm"]["bundle_key"] == "construction"


def test_resolver_unknown_industry_returns_none_when_strict() -> None:
    # Strict mode no longer raises on a no-match query; it only validates the
    # manifest-to-mapping coverage at boot. On a miss, return None so the
    # interpreter can run its LLM industry classifier stage.
    resolver = CanonicalBundleResolver(_registry(), strict_mapping=True)
    assert resolver.resolve("s1", "We are a space robotics startup") is None


def test_resolver_prioritizes_explicit_company_type_over_workflow_terms() -> None:
    resolver = CanonicalBundleResolver(_registry(), strict_mapping=True)

    result = resolver.resolve(
        "s1",
        "I own a construction company and need an internal ticketing system",
    )

    assert result is not None
    assert result.selected_bundle is not None
    assert result.selected_bundle.bundle_key == "construction"


def test_resolver_workflow_only_ticketing_text_does_not_force_bpo_industry() -> None:
    resolver = CanonicalBundleResolver(_registry(), strict_mapping=True)

    result = resolver.resolve("s1", "We need a ticketing website for internal issues")

    # Generic workflow signal should defer to upstream LLM stage
    # instead of forcing BPO industry classification.
    assert result is None


def test_resolver_hr_agency_plus_ticketing_routes_to_hr_bundle() -> None:
    resolver = CanonicalBundleResolver(_registry(), strict_mapping=True)

    result = resolver.resolve(
        "s1",
        "We are a recruitment agency and need internal ticketing for intake",
    )

    assert result is not None
    assert result.selected_bundle is not None
    assert result.selected_bundle.bundle_key == "hr_management"


def test_resolver_bpo_contact_center_stays_ticketing() -> None:
    resolver = CanonicalBundleResolver(_registry(), strict_mapping=True)

    result = resolver.resolve(
        "s1",
        "We run a BPO contact center with customer support teams",
    )

    assert result is not None
    assert result.selected_bundle is not None
    assert result.selected_bundle.bundle_key == "ticketing"


def test_payload_builder_populates_required_stores() -> None:
    builder = CanonicalPayloadBuilder(_registry())
    payload = {"stores": {}}

    populated = builder.apply_to_stores_payload("hr_management", payload)

    assert populated is True
    stores = payload["stores"]
    for key in (
        "queues",
        "projects",
        "kpis",
        "employees",
        "request_types",
        "canonical_dashboards",
    ):
        assert key in stores


def test_validation_chain_rejects_duplicate_ids() -> None:
    manifests = _registry().load_all()
    bad = dict(manifests["tenant_provisioning_bpo.jsonc"])
    bad["tickets"] = {"queues": [{"id": 1, "name": "A"}, {"id": 1, "name": "B"}]}
    manifests = {"bad.jsonc": bad}

    chain = ValidationChain(
        specs=(UniqueIdsSpec(), ReferentialIntegritySpec(), EmployeeMutableFieldsSpec())
    )
    with pytest.raises(CanonicalValidationError):
        chain.validate_all(manifests)
