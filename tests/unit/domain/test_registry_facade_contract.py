"""H2 contract test for RegistryFacade.
Locks the signatures and behavioral guarantees of get_raw_manifest() and
build_payload_stores(). Designed to break if CJ renames parameters, changes
return types, or alters the observable behavior of either method.
"""
from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

from domain.services.canonical_bundle_resolver import CanonicalBundleResolver
from domain.services.canonical_manifest_registry import CanonicalManifestRegistry
from domain.services.canonical_metadata_service import CanonicalMetadataService
from domain.services.canonical_payload_builder import CanonicalPayloadBuilder
from domain.services.registry_facade import RegistryFacade


def _facade() -> RegistryFacade:
    root = Path(__file__).resolve().parents[3]
    registry = CanonicalManifestRegistry(root / "new_json_samples")
    return RegistryFacade(
        resolver=CanonicalBundleResolver(registry, strict_mapping=True),
        payload_builder=CanonicalPayloadBuilder(registry),
        metadata_service=CanonicalMetadataService(registry),
    )


# ---------------------------------------------------------------------------
# Signature locks — these tests break if the H2 method signatures change.
# ---------------------------------------------------------------------------

def test_get_raw_manifest_parameter_names_are_locked() -> None:
    sig = inspect.signature(RegistryFacade.get_raw_manifest)
    assert list(sig.parameters) == ["self", "bundle_key"]


def test_get_raw_manifest_bundle_key_annotation_is_str() -> None:
    sig = inspect.signature(RegistryFacade.get_raw_manifest)
    assert sig.parameters["bundle_key"].annotation == "str"


def test_get_raw_manifest_return_annotation_is_locked() -> None:
    sig = inspect.signature(RegistryFacade.get_raw_manifest)
    assert "dict" in sig.return_annotation
    assert "None" in sig.return_annotation


def test_build_payload_stores_parameter_names_are_locked() -> None:
    sig = inspect.signature(RegistryFacade.build_payload_stores)
    assert list(sig.parameters) == ["self", "bundle_key", "payload_data"]


def test_build_payload_stores_bundle_key_annotation_is_str() -> None:
    sig = inspect.signature(RegistryFacade.build_payload_stores)
    assert sig.parameters["bundle_key"].annotation == "str"


def test_build_payload_stores_payload_data_annotation_is_dict() -> None:
    sig = inspect.signature(RegistryFacade.build_payload_stores)
    assert sig.parameters["payload_data"].annotation == "dict"


def test_build_payload_stores_return_annotation_is_bool() -> None:
    sig = inspect.signature(RegistryFacade.build_payload_stores)
    assert sig.return_annotation == "bool"


# ---------------------------------------------------------------------------
# Behavioral contract — these tests verify runtime behavior of both methods.
# ---------------------------------------------------------------------------

def test_get_raw_manifest_returns_dict_for_known_bundle() -> None:
    result = _facade().get_raw_manifest("ticketing")
    assert isinstance(result, dict)


def test_get_raw_manifest_contains_all_nine_manifest_keys() -> None:
    result = _facade().get_raw_manifest("ticketing")
    assert result is not None
    for key in (
        "schema_version", "session_id", "generated_at",
        "tenant", "tickets", "projects", "dashboard", "kpi", "hr_hub",
    ):
        assert key in result, f"manifest missing key: {key}"


def test_get_raw_manifest_returns_none_for_unknown_bundle() -> None:
    assert _facade().get_raw_manifest("nonexistent_bundle_xyz") is None


def test_build_payload_stores_returns_true_for_known_bundle() -> None:
    payload: dict[str, Any] = {}
    assert _facade().build_payload_stores("ticketing", payload) is True


def test_build_payload_stores_populates_all_store_keys() -> None:
    payload: dict[str, Any] = {}
    _facade().build_payload_stores("ticketing", payload)
    stores = payload.get("stores", {})
    for key in ("queues", "projects", "kpis", "employees", "request_types", "canonical_dashboards"):
        assert key in stores, f"stores missing key: {key}"


def test_build_payload_stores_returns_false_for_unknown_bundle() -> None:
    payload: dict[str, Any] = {}
    assert _facade().build_payload_stores("nonexistent_bundle_xyz", payload) is False


def test_build_payload_stores_does_not_mutate_dict_on_miss() -> None:
    payload: dict[str, Any] = {}
    _facade().build_payload_stores("nonexistent_bundle_xyz", payload)
    assert payload == {}
