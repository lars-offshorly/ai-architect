#!/usr/bin/env python3
"""Scaffold a new bundle template directory with empty JSON template files."""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import cast

BUNDLES_DIR = Path(__file__).parent.parent / "src" / "templates" / "bundles"

_PREVIEW_STUB: dict[str, object] = {
    "schema_version": "1.0",
    "bundle_key": "{bundle_key}",
    "display_name": "{display_name}",
    "modules": [],
    "stores": {},
    "metadata": {"customizable_fields": []},
}

_APP_STUB: dict[str, object] = {
    "schema_version": "1.0",
    "bundle_key": "{bundle_key}",
    "display_name": "{display_name}",
    "modules": [],
    "config": {},
    "slots_used": [],
}

_DUMMY_DATA_STUB: dict[str, object] = {
    "schema_version": "1.0",
    "bundle_key": "{bundle_key}",
    "stores": {},
}


def _fill(
    stub: Mapping[str, object], bundle_key: str, display_name: str
) -> dict[str, object]:
    raw = json.dumps(stub)
    raw = raw.replace("{bundle_key}", bundle_key).replace(
        "{display_name}", display_name
    )
    return cast(dict[str, object], json.loads(raw))


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Usage: generate_templates.py <bundle_key> [display_name]")
        return 1

    bundle_key = argv[1]
    display_name = argv[2] if len(argv) > 2 else bundle_key.replace("_", " ").title()
    bundle_dir = BUNDLES_DIR / bundle_key

    if bundle_dir.exists():
        print(f"Bundle directory already exists: {bundle_dir}")
        return 1

    bundle_dir.mkdir(parents=True)
    files = {
        "preview.json": _fill(_PREVIEW_STUB, bundle_key, display_name),
        "app.json": _fill(_APP_STUB, bundle_key, display_name),
        "dummy_data.json": _fill(_DUMMY_DATA_STUB, bundle_key, display_name),
    }
    for filename, content in files.items():
        path = bundle_dir / filename
        path.write_text(json.dumps(content, indent=2), encoding="utf-8")
        print(f"Created: {path}")

    print(f"\nBundle '{bundle_key}' scaffolded. Fill in modules, config, and stores.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
