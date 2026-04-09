#!/usr/bin/env python3
"""Print or write seed dummy data for a specific bundle to stdout or a file."""

from __future__ import annotations

import json
import sys
from pathlib import Path

BUNDLES_DIR = Path(__file__).parent.parent / "src" / "templates" / "bundles"


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        available_bundles = [d.name for d in BUNDLES_DIR.iterdir() if d.is_dir()]
        print("Usage: seed_dummy_data.py <bundle_key> [output_path]")
        print(f"Available bundles: {available_bundles}")
        return 1

    bundle_key = argv[1]
    dummy_path = BUNDLES_DIR / bundle_key / "dummy_data.json"

    if not dummy_path.exists():
        print(f"No dummy_data.json found for bundle '{bundle_key}': {dummy_path}")
        return 1

    data = json.loads(dummy_path.read_text(encoding="utf-8"))

    if len(argv) > 2:
        output_path = Path(argv[2])
        output_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"Written to {output_path}")
    else:
        print(json.dumps(data, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
