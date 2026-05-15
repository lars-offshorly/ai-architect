from __future__ import annotations

from pathlib import Path

import pytest

from domain.services.canonical_bundle_resolver import CanonicalBundleResolver
from domain.services.canonical_manifest_registry import (
    CanonicalManifestRegistry,
    CanonicalManifestRegistryError,
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


def test_resolver_unknown_industry_fallback_when_not_strict() -> None:
    resolver = CanonicalBundleResolver(_registry(), strict_mapping=False)

    result = resolver.resolve("s1", "We are a space robotics startup")

    assert result.selected_bundle is not None
    assert result.selected_bundle.bundle_key == "generic"
    assert result.confidence_status == "fallback_generic"


def test_mapping_file_is_loaded() -> None:
    mapping = _registry().industry_bundle_map()
    assert mapping["construction_firm"]["bundle_key"] == "construction"


def test_resolver_unknown_industry_raises_when_strict() -> None:
    resolver = CanonicalBundleResolver(_registry(), strict_mapping=True)
    with pytest.raises(CanonicalManifestRegistryError):
        resolver.resolve("s1", "We are a space robotics startup")


def test_payload_builder_populates_required_stores() -> None:
    builder = CanonicalPayloadBuilder(_registry())
    payload = {"stores": {}}

    populated = builder.apply_to_dummy_data("hr_management", payload)

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
