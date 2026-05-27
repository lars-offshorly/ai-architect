from __future__ import annotations

import json
from pathlib import Path

import pytest

from domain.services.canonical_manifest_registry import CanonicalManifestRegistry
from domain.services.canonical_manifest_registry import CanonicalManifestRegistryError


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


def _write_manifest_dir(
    root: Path,
    *,
    schema_version: str,
    mode: str,
    active_versions: list[str],
    deprecated_versions: list[str] | None = None,
    use_v2_1_stores_shape: bool = False,
) -> None:
    manifests_dir = root / "new_json_samples"
    manifests_dir.mkdir(parents=True, exist_ok=True)
    if use_v2_1_stores_shape:
        payload = {
            "schema_version": schema_version,
            "session_id": "s1",
            "generated_at": "2026-01-01T00:00:00Z",
            "tenant": {"industry": "bpo_contact_center"},
            "stores": {
                "queues": [{"id": 1, "name": "Support"}],
                "projects": [{"id": 10, "name": "Migration"}],
                "dashboards": [{"id": 20, "name": "Ops"}],
                "kpis": [{"id": 30, "name": "CSAT"}],
                "employees": [{"id": "e1", "position": "Agent", "team": "L1", "department": "Ops", "job_title": "Agent", "job_type": "Full-time", "job_level": "IC"}],
                "request_types": [{"id": 40, "name": "Leave"}],
            },
        }
    else:
        payload = {
            "schema_version": schema_version,
            "session_id": "s1",
            "generated_at": "2026-01-01T00:00:00Z",
            "tenant": {"industry": "bpo_contact_center"},
            "tickets": {"queues": []},
            "projects": {"projects": []},
            "dashboard": {"dashboards": []},
            "kpi": {"kpis": []},
            "hr_hub": {"employees": [], "request_types": []},
        }
    (manifests_dir / "tenant_provisioning_bpo.jsonc").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    mapping = {
        "schema_version": "1.0",
        "mappings": {
            "bpo_contact_center": {
                "bundle_key": "ticketing",
                "aliases": ["bpo"],
            }
        },
    }
    (manifests_dir / "industry_bundle_map.json").write_text(
        json.dumps(mapping), encoding="utf-8"
    )
    policy = {
        "schema_version": "1.0",
        "mode": mode,
        "active_versions": active_versions,
        "deprecated_versions": deprecated_versions or [],
        "default_version": active_versions[0],
    }
    (manifests_dir / "schema_policy.json").write_text(
        json.dumps(policy), encoding="utf-8"
    )


def test_schema_policy_strict_rejects_deprecated(tmp_path: Path) -> None:
    _write_manifest_dir(
        tmp_path,
        schema_version="1.0",
        mode="strict",
        active_versions=["2.0"],
        deprecated_versions=["1.0"],
    )
    registry = CanonicalManifestRegistry(tmp_path / "new_json_samples")
    with pytest.raises(CanonicalManifestRegistryError):
        registry.load_all()


def test_schema_policy_compat_allows_deprecated(tmp_path: Path) -> None:
    _write_manifest_dir(
        tmp_path,
        schema_version="1.0",
        mode="compat",
        active_versions=["2.0"],
        deprecated_versions=["1.0"],
    )
    registry = CanonicalManifestRegistry(tmp_path / "new_json_samples")
    manifests = registry.load_all()
    assert "tenant_provisioning_bpo.jsonc" in manifests
    policy = registry.schema_policy()
    assert policy.get("deprecated_found")


def test_schema_policy_latest_only_enforces_latest_active(tmp_path: Path) -> None:
    _write_manifest_dir(
        tmp_path,
        schema_version="2.0",
        mode="latest_only",
        active_versions=["2.0", "2.1"],
    )
    registry = CanonicalManifestRegistry(tmp_path / "new_json_samples")
    with pytest.raises(CanonicalManifestRegistryError):
        registry.load_all()


def test_v2_1_stores_shape_is_normalized_by_adapter(tmp_path: Path) -> None:
    _write_manifest_dir(
        tmp_path,
        schema_version="2.1",
        mode="strict",
        active_versions=["2.1"],
        use_v2_1_stores_shape=True,
    )
    registry = CanonicalManifestRegistry(tmp_path / "new_json_samples")
    manifests = registry.load_all()
    payload = manifests["tenant_provisioning_bpo.jsonc"]
    assert payload["tickets"]["queues"][0]["name"] == "Support"
    assert payload["projects"]["projects"][0]["name"] == "Migration"
    assert payload["dashboard"]["dashboards"][0]["name"] == "Ops"
