"""Unit tests for dashboard/templates.py — DashboardTemplateRegistry."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from agents.preview_generator.dashboard.templates import (
    DashboardTemplateRegistry,
    _BUNDLE_TO_TEMPLATE,
)
from catalog.bundle_catalog import BundleVariantDefinition

_SAMPLE_TEMPLATE = {
    "source_template": "sample_template",
    "generated_at": "2026-04-20",
    "widgets": [
        {
            "type": "number",
            "title": "Total Count",
            "position": {"row": 0, "col": 0, "width": 3, "height": 3},
        }
    ],
}


@pytest.fixture
def templates_dir(tmp_path: Path) -> Path:
    """Write all templates referenced by _BUNDLE_TO_TEMPLATE into a temp dir."""
    filenames = set(_BUNDLE_TO_TEMPLATE.values())
    for filename in filenames:
        template = dict(_SAMPLE_TEMPLATE)
        template["source_template"] = filename
        (tmp_path / f"{filename}.json").write_text(json.dumps(template))
    return tmp_path


@pytest.fixture
def registry(templates_dir: Path) -> DashboardTemplateRegistry:
    return DashboardTemplateRegistry(templates_dir=templates_dir)


# ---------------------------------------------------------------------------
# Resolution — known bundles
# ---------------------------------------------------------------------------


def test_hr_management_returns_template(registry: DashboardTemplateRegistry):
    result = registry.get("hr_management")
    assert result is not None
    assert isinstance(result, dict)
    assert "source_template" in result


def test_hr_hub_alias_resolves_same_as_hr_management(registry: DashboardTemplateRegistry):
    hr_management = registry.get("hr_management")
    hr_hub = registry.get("hr_hub")
    assert hr_management is not None
    assert hr_hub is not None
    assert hr_management["source_template"] == hr_hub["source_template"]


def test_project_mgmt_returns_template(registry: DashboardTemplateRegistry):
    result = registry.get("project_mgmt")
    assert result is not None
    assert "widgets" in result


# ---------------------------------------------------------------------------
# Resolution — unknown / Tier 3 bundles
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bundle_key",
    ["finance", "marketing", "sales"],
)
def test_mapped_bundles_return_template(
    bundle_key: str, registry: DashboardTemplateRegistry
):
    """Bundles listed in _BUNDLE_TO_TEMPLATE resolve without a catalog."""
    result = registry.get(bundle_key)
    assert result is not None
    assert result["source_template"] == bundle_key


def test_unknown_bundle_returns_none(registry: DashboardTemplateRegistry):
    assert registry.get("unknown_bundle") is None


# ---------------------------------------------------------------------------
# Deep copy — mutations don't affect the cache
# ---------------------------------------------------------------------------


def test_get_returns_deep_copy(registry: DashboardTemplateRegistry):
    copy1 = registry.get("hr_management")
    assert copy1 is not None
    copy1["source_template"] = "mutated"

    copy2 = registry.get("hr_management")
    assert copy2 is not None
    assert copy2["source_template"] != "mutated"


def test_mutating_widgets_does_not_affect_cache(registry: DashboardTemplateRegistry):
    copy1 = registry.get("project_mgmt")
    assert copy1 is not None
    copy1["widgets"].append({"type": "extra"})

    copy2 = registry.get("project_mgmt")
    assert copy2 is not None
    original_length = len(_SAMPLE_TEMPLATE["widgets"])
    assert len(copy2["widgets"]) == original_length


# ---------------------------------------------------------------------------
# Missing / invalid files
# ---------------------------------------------------------------------------


def test_empty_templates_dir_returns_none(tmp_path: Path):
    registry = DashboardTemplateRegistry(templates_dir=tmp_path)
    assert registry.get("hr_management") is None


def test_missing_templates_dir_logs_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
):
    import logging

    missing = tmp_path / "does-not-exist"
    with caplog.at_level(logging.WARNING):
        DashboardTemplateRegistry(templates_dir=missing)

    assert any("not found" in rec.message for rec in caplog.records)


def test_invalid_json_logs_warning_and_returns_none(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
):
    import logging

    (tmp_path / "hr_management.json").write_text("{ invalid json }")

    with caplog.at_level(logging.WARNING):
        registry = DashboardTemplateRegistry(templates_dir=tmp_path)

    result = registry.get("hr_management")
    assert result is None


# ---------------------------------------------------------------------------
# supported_bundles
# ---------------------------------------------------------------------------


def test_supported_bundles_contains_known_keys(registry: DashboardTemplateRegistry):
    supported = registry.supported_bundles()
    assert "hr_management" in supported
    assert "hr_hub" in supported
    assert "project_mgmt" in supported


def test_supported_bundles_contains_mapped_keys(
    registry: DashboardTemplateRegistry,
):
    supported = registry.supported_bundles()
    assert "finance" in supported
    assert "marketing" in supported
    assert "sales" in supported


# ---------------------------------------------------------------------------
# Catalog-backed variant resolution
# ---------------------------------------------------------------------------


def _variant(key: str, template: str, is_default: bool = False) -> BundleVariantDefinition:
    return BundleVariantDefinition(
        key=key,
        display_name=key,
        description="",
        is_default=is_default,
        dashboard_template=template,
    )


def _make_catalog(bundle_key: str, variants: list) -> MagicMock:
    catalog = MagicMock()
    catalog.get_variants.return_value = variants
    catalog.get_variant.side_effect = lambda bk, vk: next(
        (v for v in variants if bk == bundle_key and v.key == vk), None
    )
    catalog.get_default_variant.return_value = next(
        (v for v in variants if v.is_default), None
    )
    return catalog


@pytest.fixture
def variant_templates_dir(tmp_path: Path) -> Path:
    """Write templates referenced by fallback map + variant-specific templates."""
    for filename in set(_BUNDLE_TO_TEMPLATE.values()) | {
        "hr_management_recruiting",
        "hr_management_onboarding",
    }:
        template = dict(_SAMPLE_TEMPLATE)
        template["source_template"] = filename
        (tmp_path / f"{filename}.json").write_text(json.dumps(template))
    return tmp_path


def test_variant_key_resolves_via_catalog(variant_templates_dir: Path):
    variants = [
        _variant("app-01", "hr_management", is_default=True),
        _variant("app-02", "hr_management_recruiting"),
        _variant("app-03", "hr_management_onboarding"),
    ]
    catalog = _make_catalog("hr_management", variants)
    registry = DashboardTemplateRegistry(
        templates_dir=variant_templates_dir, catalog=catalog
    )

    result = registry.get("hr_management", variant_key="app-02")

    assert result is not None
    assert result["source_template"] == "hr_management_recruiting"


def test_missing_variant_key_falls_back_to_default(variant_templates_dir: Path):
    variants = [
        _variant("app-01", "hr_management", is_default=True),
        _variant("app-02", "hr_management_recruiting"),
    ]
    catalog = _make_catalog("hr_management", variants)
    registry = DashboardTemplateRegistry(
        templates_dir=variant_templates_dir, catalog=catalog
    )

    # Unknown variant key → default (app-01).
    result = registry.get("hr_management", variant_key="app-99")

    assert result is not None
    assert result["source_template"] == "hr_management"


def test_bundle_without_variants_uses_fallback_map(variant_templates_dir: Path):
    catalog = _make_catalog("ticketing", [])
    registry = DashboardTemplateRegistry(
        templates_dir=variant_templates_dir, catalog=catalog
    )

    result = registry.get("ticketing", variant_key="app-02")

    assert result is not None
    assert result["source_template"] == "ticketing"
