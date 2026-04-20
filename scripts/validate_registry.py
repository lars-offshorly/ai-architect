#!/usr/bin/env python3
"""Validate bundle_registry.yaml for correctness and completeness.

Checks:
1. Unique bundle_keys
2. Required fields present for each bundle
3. Template directories exist
4. Metadata sections complete
5. Signal boosts are valid floats
6. No duplicate synonyms across bundles (warning only)
7. Template files exist (preview.json, app.json, dummy_data.json)
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

# Add project root to path for imports when run as a standalone script.
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

REGISTRY_PATH = (
    Path(__file__).parent.parent / "src" / "templates" / "bundle_registry.yaml"
)
TEMPLATES_BASE = Path(__file__).parent.parent / "src" / "templates" / "bundles"

REQUIRED_BUNDLE_FIELDS = [
    "bundle_key",
    "display_name",
    "primary_entity",
    "description",
    "template_dir",
    "default_modules",
    "typical_entities",
    "typical_intents",
    "required_signals",
]

REQUIRED_METADATA_FIELDS = [
    "kpis",
    "workflows",
    "entity_definitions",
]


def validate_registry_structure(registry_path: Path) -> tuple[list[str], list[str]]:
    """Validate registry YAML structure and return (errors, warnings)."""
    errors: list[str] = []
    warnings: list[str] = []

    if not registry_path.exists():
        errors.append(f"Registry file not found: {registry_path}")
        return errors, warnings

    try:
        with open(registry_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        errors.append(f"Invalid YAML: {exc}")
        return errors, warnings

    if not isinstance(data, dict) or "bundles" not in data:
        errors.append("Registry must contain top-level 'bundles' list")
        return errors, warnings

    bundles = data["bundles"]
    if not isinstance(bundles, list):
        errors.append("'bundles' must be a list")
        return errors, warnings

    if not bundles:
        errors.append("No bundles defined in registry")
        return errors, warnings

    return errors, warnings


def validate_bundle_uniqueness(bundles: list[dict]) -> list[str]:
    """Check bundle_key uniqueness."""
    errors: list[str] = []
    bundle_keys = [b.get("bundle_key") for b in bundles]
    duplicates = {key for key in bundle_keys if bundle_keys.count(key) > 1}
    if duplicates:
        errors.append(f"Duplicate bundle_keys found: {duplicates}")
    return errors


def validate_bundle_fields(bundle: dict, bundle_idx: int) -> list[str]:
    """Validate required fields for a single bundle."""
    errors: list[str] = []
    bundle_key = bundle.get("bundle_key", f"<bundle {bundle_idx}>")

    for field in REQUIRED_BUNDLE_FIELDS:
        if field not in bundle or not bundle[field]:
            errors.append(f"Bundle '{bundle_key}': missing or empty field '{field}'")

    return errors


def validate_signal_boosts(bundle: dict) -> list[str]:
    """Validate signal_boosts are valid floats."""
    errors: list[str] = []
    bundle_key = bundle.get("bundle_key", "<unknown>")
    signal_boosts = bundle.get("signal_boosts", {})

    if not isinstance(signal_boosts, dict):
        errors.append(f"Bundle '{bundle_key}': signal_boosts must be a dict")
        return errors

    for signal, boost in signal_boosts.items():
        try:
            float_boost = float(boost)
            if float_boost < 0 or float_boost > 1:
                errors.append(
                    f"Bundle '{bundle_key}': signal_boost for '{signal}' "
                    f"({float_boost}) should be between 0.0 and 1.0"
                )
        except (ValueError, TypeError):
            errors.append(
                "Bundle "
                f"'{bundle_key}': signal_boost for '{signal}' "
                f"is not a valid number: {boost}"
            )

    return errors


def validate_metadata_section(bundle: dict) -> tuple[list[str], list[str]]:
    """Validate metadata section completeness."""
    errors: list[str] = []
    warnings: list[str] = []
    bundle_key = bundle.get("bundle_key", "<unknown>")
    metadata = bundle.get("metadata")

    if not metadata:
        warnings.append(f"Bundle '{bundle_key}': no metadata section")
        return errors, warnings

    if not isinstance(metadata, dict):
        errors.append(f"Bundle '{bundle_key}': metadata must be a dict")
        return errors, warnings

    for field in REQUIRED_METADATA_FIELDS:
        if field not in metadata:
            warnings.append(f"Bundle '{bundle_key}': metadata missing field '{field}'")

    return errors, warnings


def validate_template_paths(bundle: dict) -> tuple[list[str], list[str]]:
    """Validate template directories and files exist."""
    errors: list[str] = []
    warnings: list[str] = []
    bundle_key = bundle.get("bundle_key", "<unknown>")
    template_dir = bundle.get("template_dir")

    if not template_dir:
        return errors, warnings  # Already caught by required fields check

    bundle_dir = TEMPLATES_BASE / template_dir
    if not bundle_dir.exists():
        errors.append(
            f"Bundle '{bundle_key}': template directory not found: {bundle_dir}"
        )
        return errors, warnings

    if not bundle_dir.is_dir():
        errors.append(
            f"Bundle '{bundle_key}': template_dir is not a directory: {bundle_dir}"
        )
        return errors, warnings

    # Check for expected template files
    required_files = ["preview.json", "app.json"]
    optional_files = ["dummy_data.json"]

    for filename in required_files:
        file_path = bundle_dir / filename
        if not file_path.exists():
            errors.append(
                f"Bundle '{bundle_key}': required template file missing: {file_path}"
            )

    for filename in optional_files:
        file_path = bundle_dir / filename
        if not file_path.exists():
            warnings.append(
                f"Bundle '{bundle_key}': optional template file missing: {file_path}"
            )

    return errors, warnings


def check_synonym_overlap(bundles: list[dict]) -> list[str]:
    """Check for synonym overlap between bundles (warning only)."""
    warnings: list[str] = []
    synonym_map: dict[str, list[str]] = {}

    for bundle in bundles:
        bundle_key = bundle.get("bundle_key", "<unknown>")
        synonyms = bundle.get("synonyms", [])
        for synonym in synonyms:
            synonym_lower = synonym.lower()
            if synonym_lower not in synonym_map:
                synonym_map[synonym_lower] = []
            synonym_map[synonym_lower].append(bundle_key)

    for synonym, bundle_keys in synonym_map.items():
        if len(bundle_keys) > 1:
            warnings.append(
                f"Synonym '{synonym}' appears in multiple bundles: {bundle_keys}"
            )

    return warnings


def validate_catalog_loading() -> tuple[list[str], list[str]]:
    """Try loading catalog via BundleCatalog to catch Pydantic + variant errors.

    Runs ``BundleCatalog.validate`` (template_dir consistency) AND
    ``BundleCatalog.validate_variants`` (default-count, unique keys,
    on-disk app-0*.json and dashboard_output_templates/*.json presence).
    """
    errors: list[str] = []
    warnings: list[str] = []

    try:
        # pylint: disable=import-outside-toplevel
        from catalog.bundle_catalog import BundleCatalog
        from core.exceptions import BundleRegistryValidationError

        catalog = BundleCatalog(catalog_path=REGISTRY_PATH)
        num_bundles = len(catalog._bundles)  # pylint: disable=protected-access
        print(f"✓ Catalog loaded successfully: {num_bundles} bundles")

        catalog.validate(templates_dir=TEMPLATES_BASE)
        catalog.validate_variants(templates_dir=TEMPLATES_BASE)
        print("✓ Variant validation passed")
    except BundleRegistryValidationError as exc:
        errors.append(f"Catalog validation failed: {exc}")
    except Exception as exc:  # pylint: disable=broad-except
        errors.append(f"Catalog loading failed: {exc}")

    return errors, warnings


def validate_no_stray_keywords() -> list[str]:
    """Ensure ``keywords`` lives only in bundle_registry.yaml variants.

    Legacy ``keywords`` fields in ``app-0*.json`` /
    ``dashboard_output_templates/*.json`` were removed once variant
    selection moved into the catalog. Re-introducing them silently desyncs
    the source of truth, so we fail loudly.
    """
    import json  # pylint: disable=import-outside-toplevel

    errors: list[str] = []
    app_files = list(TEMPLATES_BASE.glob("*/app-0*.json"))
    outputs_base = Path(__file__).parent.parent / "dashboard_output_templates"
    output_files = list(outputs_base.glob("*.json")) if outputs_base.is_dir() else []

    for path in app_files + output_files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(data, dict) and "keywords" in data:
            errors.append(
                "Stray 'keywords' field in "
                f"{path.relative_to(Path(__file__).parent.parent)}; "
                "move to variants block in bundle_registry.yaml."
            )
    return errors


def main() -> int:
    """Run all validations and report results."""
    print(f"Validating bundle registry: {REGISTRY_PATH}\n")

    all_errors: list[str] = []
    all_warnings: list[str] = []

    # Step 1: Validate structure
    struct_errors, struct_warnings = validate_registry_structure(REGISTRY_PATH)
    all_errors += struct_errors
    all_warnings += struct_warnings

    if struct_errors:
        # Cannot continue if structure is invalid
        print_results(all_errors, all_warnings)
        return 1

    # Load bundles
    with open(REGISTRY_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    bundles = data["bundles"]

    # Step 2: Validate uniqueness
    all_errors += validate_bundle_uniqueness(bundles)

    # Step 3: Validate each bundle
    for idx, bundle in enumerate(bundles):
        all_errors += validate_bundle_fields(bundle, idx)
        all_errors += validate_signal_boosts(bundle)

        meta_errors, meta_warnings = validate_metadata_section(bundle)
        all_errors += meta_errors
        all_warnings += meta_warnings

        path_errors, path_warnings = validate_template_paths(bundle)
        all_errors += path_errors
        all_warnings += path_warnings

    # Step 4: Check synonym overlap (warnings only)
    all_warnings += check_synonym_overlap(bundles)

    # Step 5: Try loading with BundleCatalog (includes variant validation)
    load_errors, load_warnings = validate_catalog_loading()
    all_errors += load_errors
    all_warnings += load_warnings

    # Step 6: Ensure no stray 'keywords' outside the registry
    all_errors += validate_no_stray_keywords()

    # Report results
    print_results(all_errors, all_warnings)

    if all_errors:
        return 1

    print("\n✓ Registry validation passed!")
    return 0


def print_results(errors: list[str], warnings: list[str]) -> None:
    """Print validation results."""
    if errors:
        print(f"\n{len(errors)} Error(s):")
        for error in errors:
            print(f"  ✗ {error}")

    if warnings:
        print(f"\n{len(warnings)} Warning(s):")
        for warning in warnings:
            print(f"  ⚠ {warning}")


if __name__ == "__main__":
    sys.exit(main())
