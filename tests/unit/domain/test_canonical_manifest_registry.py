from __future__ import annotations

from pathlib import Path

from domain.services.canonical_manifest_registry import CanonicalManifestRegistry


def test_loads_canonical_jsonc_samples() -> None:
    root = Path(__file__).resolve().parents[3]
    registry = CanonicalManifestRegistry(root / "new_json_samples")

    manifests = registry.load_all()
    assert len(manifests) >= 3

    industries = registry.by_industry()
    assert "bpo_contact_center" in industries
    assert "construction_firm" in industries
    assert "hr_recruitment_agency" in industries


def test_manifest_shape_has_mutable_surfaces() -> None:
    root = Path(__file__).resolve().parents[3]
    registry = CanonicalManifestRegistry(root / "new_json_samples")

    manifests = registry.load_all()
    sample = manifests["tenant_provisioning_bpo.jsonc"]

    assert isinstance(sample["hr_hub"]["employees"], list)
    assert isinstance(sample["tickets"]["queues"], list)
    assert isinstance(sample["projects"]["projects"], list)
    assert isinstance(sample["dashboard"]["dashboards"], list)
    assert isinstance(sample["kpi"]["kpis"], list)
    assert isinstance(sample["hr_hub"]["request_types"], list)
