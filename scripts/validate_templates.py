#!/usr/bin/env python3
"""Validate all bundle template JSON files against required schema keys.

The repository now uses two layout styles:
- variant bundles: ``app.json`` + ``app-0*.json``
- legacy bundles: ``preview.json`` + ``app.json`` + ``dummy_data.json``

This validator accepts both, but checks the correct contract for each style.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BUNDLES_DIR = Path(__file__).parent.parent / "src" / "templates" / "bundles"

ACTIVE_APP_REQUIRED = {"schema_version", "bundle_key", "config", "stores_contract"}
VARIANT_REQUIRED = {"schema_version", "bundle_key", "stores"}
LEGACY_PREVIEW_REQUIRED = {"schema_version", "bundle_key", "stores"}
LEGACY_DUMMY_REQUIRED = {"bundle_key", "stores"}


def validate_file(path: Path, required_keys: set[str]) -> list[str]:
    errors: list[str] = []
    if not path.exists():
        errors.append(f"MISSING: {path}")
        return errors
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"INVALID JSON {path}: {exc}")
        return errors
    missing = required_keys - data.keys()
    if missing:
        errors.append(f"MISSING KEYS in {path}: {missing}")
    return errors


def _has_variant_files(bundle_dir: Path) -> bool:
    return any(bundle_dir.glob("app-0*.json"))


def main() -> int:
    all_errors: list[str] = []
    bundle_dirs = [d for d in BUNDLES_DIR.iterdir() if d.is_dir()]
    if not bundle_dirs:
        print(f"No bundle directories found in {BUNDLES_DIR}")
        return 1

    for bundle_dir in sorted(bundle_dirs):
        json_files = list(bundle_dir.glob("*.json"))
        if not json_files:
            continue
        all_errors += validate_file(bundle_dir / "app.json", ACTIVE_APP_REQUIRED)
        if _has_variant_files(bundle_dir):
            for variant_file in sorted(bundle_dir.glob("app-0*.json")):
                all_errors += validate_file(variant_file, VARIANT_REQUIRED)
        else:
            all_errors += validate_file(
                bundle_dir / "preview.json", LEGACY_PREVIEW_REQUIRED
            )
            all_errors += validate_file(
                bundle_dir / "dummy_data.json", LEGACY_DUMMY_REQUIRED
            )

    if all_errors:
        print("Validation FAILED:")
        for error in all_errors:
            print(f"  ✗ {error}")
        return 1

    print(f"All {len(bundle_dirs)} bundle(s) validated successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
