#!/usr/bin/env python3
from __future__ import annotations

# pylint: disable=wrong-import-position
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from domain.services.canonical_manifest_registry import (  # noqa: E402
    CanonicalManifestRegistry,
    CanonicalManifestRegistryError,
)
from domain.services.canonical_validation import (  # noqa: E402
    CanonicalValidationError,
    EmployeeMutableFieldsSpec,
    ReferentialIntegritySpec,
    UniqueIdsSpec,
    ValidationChain,
)


def main() -> int:
    registry = CanonicalManifestRegistry(ROOT / "new_json_samples")
    try:
        manifests = registry.load_all()
        policy = registry.schema_policy()
        registry.validate_mapping_coverage()
        ValidationChain(
            specs=(
                UniqueIdsSpec(),
                ReferentialIntegritySpec(),
                EmployeeMutableFieldsSpec(),
            )
        ).validate_all(manifests)
    except CanonicalManifestRegistryError as exc:
        print(f"✗ canonical manifest validation failed: {exc}")
        return 1
    except CanonicalValidationError as exc:
        print(f"✗ canonical validation spec failed:\n{exc}")
        return 1

    industries = sorted(registry.by_industry().keys())
    print(f"✓ loaded {len(manifests)} canonical manifests")
    print(f"✓ industries: {', '.join(industries)}")
    print(
        "✓ schema policy: "
        f"mode={policy['mode']} active={policy['active_versions']} "
        "deprecated="
        f"{policy['deprecated_versions']} default={policy['default_version']}"
    )
    deprecated_found = policy.get("deprecated_found", [])
    if deprecated_found:
        print(
            "⚠ deprecated schema versions used (compat mode): "
            + ", ".join(deprecated_found)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
