#!/usr/bin/env python3
"""Validate all bundle template JSON files against required schema keys."""

from __future__ import annotations

import json
import sys
from pathlib import Path

BUNDLES_DIR = Path(__file__).parent.parent / "src" / "templates" / "bundles"

PREVIEW_REQUIRED = {"schema_version", "bundle_key", "stores"}
APP_REQUIRED = {"schema_version", "bundle_key", "modules", "config"}
DUMMY_REQUIRED = {"bundle_key", "stores"}


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


def main() -> int:
    all_errors: list[str] = []
    bundle_dirs = [d for d in BUNDLES_DIR.iterdir() if d.is_dir()]
    if not bundle_dirs:
        print(f"No bundle directories found in {BUNDLES_DIR}")
        return 1

    for bundle_dir in sorted(bundle_dirs):
        all_errors += validate_file(bundle_dir / "preview.json", PREVIEW_REQUIRED)
        all_errors += validate_file(bundle_dir / "app.json", APP_REQUIRED)
        all_errors += validate_file(bundle_dir / "dummy_data.json", DUMMY_REQUIRED)

    if all_errors:
        print("Validation FAILED:")
        for error in all_errors:
            print(f"  ✗ {error}")
        return 1

    print(f"All {len(bundle_dirs)} bundle(s) validated successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
