from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .canonical_adapters import normalize_manifest_for_runtime


class CanonicalManifestRegistryError(RuntimeError):
    """Raised when canonical manifest files are missing or invalid."""


_JSONC_LINE_COMMENT_RE = re.compile(r"(^|[^:\\])//.*$")
_VALID_POLICY_MODES = {"strict", "compat", "latest_only"}


class CanonicalManifestRegistry:
    """Loads canonical tenant provisioning manifests from ``new_json_samples``.

    These JSONC files are the authoritative provisioning contract. Only files in
    this directory are considered canonical.
    """

    def __init__(self, manifests_dir: Path | str = "new_json_samples") -> None:
        self._dir = Path(manifests_dir)
        self._cache: dict[str, dict[str, Any]] = {}
        self._mapping_cache: dict[str, dict[str, Any]] | None = None
        self._policy_cache: dict[str, Any] | None = None

    def list_files(self) -> list[Path]:
        if not self._dir.is_dir():
            raise CanonicalManifestRegistryError(
                f"Canonical manifests directory not found: {self._dir}"
            )
        return sorted(self._dir.glob("*.jsonc"))

    def load_all(self) -> dict[str, dict[str, Any]]:
        manifests: dict[str, dict[str, Any]] = {}
        for path in self.list_files():
            manifests[path.name] = self._load_one(path)
        if not manifests:
            raise CanonicalManifestRegistryError(
                f"No canonical manifests found under: {self._dir}"
            )
        self._validate_schema_versions(manifests)
        self._cache = manifests
        return dict(manifests)

    def schema_policy(self) -> dict[str, Any]:
        if self._policy_cache is not None:
            return dict(self._policy_cache)

        path = self._dir / "schema_policy.json"
        if not path.exists():
            # Safe default for existing deployments that have not created policy yet.
            default = {
                "mode": "strict",
                "active_versions": ["2.0"],
                "deprecated_versions": [],
                "default_version": "2.0",
            }
            self._policy_cache = default
            return dict(default)

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CanonicalManifestRegistryError(
                f"Invalid schema policy file: {path}"
            ) from exc

        mode = data.get("mode", "strict")
        if not isinstance(mode, str) or mode not in _VALID_POLICY_MODES:
            raise CanonicalManifestRegistryError(
                "schema_policy.mode must be one of: "
                f"{', '.join(sorted(_VALID_POLICY_MODES))}"
            )
        active_versions = data.get("active_versions", [])
        deprecated_versions = data.get("deprecated_versions", [])
        default_version = data.get("default_version")

        if not isinstance(active_versions, list) or not active_versions:
            raise CanonicalManifestRegistryError(
                "schema_policy.active_versions must be a non-empty list"
            )
        if not isinstance(deprecated_versions, list):
            raise CanonicalManifestRegistryError(
                "schema_policy.deprecated_versions must be a list"
            )
        if not isinstance(default_version, str) or not default_version.strip():
            raise CanonicalManifestRegistryError(
                "schema_policy.default_version must be a non-empty string"
            )

        normalized_active = _normalize_versions(active_versions, "active_versions")
        normalized_deprecated = _normalize_versions(
            deprecated_versions, "deprecated_versions"
        )

        if default_version not in normalized_active:
            raise CanonicalManifestRegistryError(
                "schema_policy.default_version must exist in active_versions"
            )
        overlap = sorted(set(normalized_active).intersection(normalized_deprecated))
        if overlap:
            raise CanonicalManifestRegistryError(
                "schema_policy active/deprecated overlap: " + ", ".join(overlap)
            )

        policy = {
            "mode": mode,
            "active_versions": normalized_active,
            "deprecated_versions": normalized_deprecated,
            "default_version": default_version,
        }
        self._policy_cache = policy
        return dict(policy)

    def by_industry(self) -> dict[str, dict[str, Any]]:
        manifests = self._cache or self.load_all()
        indexed: dict[str, dict[str, Any]] = {}
        for payload in manifests.values():
            tenant = payload.get("tenant")
            if not isinstance(tenant, dict):
                continue
            industry = tenant.get("industry")
            if isinstance(industry, str) and industry.strip():
                indexed[industry] = payload
        return indexed

    def industry_bundle_map(self) -> dict[str, dict[str, Any]]:
        if self._mapping_cache is not None:
            return dict(self._mapping_cache)
        path = self._dir / "industry_bundle_map.json"
        if not path.exists():
            raise CanonicalManifestRegistryError(
                f"Industry mapping file not found: {path}"
            )
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CanonicalManifestRegistryError(
                f"Invalid industry mapping file: {path}"
            ) from exc
        mappings = data.get("mappings")
        if not isinstance(mappings, dict) or not mappings:
            raise CanonicalManifestRegistryError(
                f"Industry mapping file has no mappings: {path}"
            )
        normalized: dict[str, dict[str, Any]] = {}
        for industry, value in mappings.items():
            if not isinstance(industry, str) or not industry.strip():
                raise CanonicalManifestRegistryError(
                    f"Industry mapping contains invalid key: {industry!r}"
                )
            if not isinstance(value, dict):
                raise CanonicalManifestRegistryError(
                    f"Industry mapping for '{industry}' must be object"
                )
            bundle_key = value.get("bundle_key")
            if not isinstance(bundle_key, str) or not bundle_key.strip():
                raise CanonicalManifestRegistryError(
                    f"Industry mapping for '{industry}' missing bundle_key"
                )
            aliases = value.get("aliases", [])
            if not isinstance(aliases, list) or not all(
                isinstance(a, str) for a in aliases
            ):
                raise CanonicalManifestRegistryError(
                    f"Industry mapping for '{industry}' has invalid aliases"
                )
            normalized[industry] = {
                "bundle_key": bundle_key,
                "aliases": [a for a in aliases if a.strip()],
            }
        self._mapping_cache = normalized
        return dict(normalized)

    def validate_mapping_coverage(self) -> None:
        manifest_industries = set(self.by_industry().keys())
        mapped_industries = set(self.industry_bundle_map().keys())
        missing = sorted(manifest_industries - mapped_industries)
        if missing:
            raise CanonicalManifestRegistryError(
                "Industry mapping missing entries for manifest industries: "
                f"{', '.join(missing)}"
            )

    def _load_one(self, path: Path) -> dict[str, Any]:
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise CanonicalManifestRegistryError(f"Failed to read {path}") from exc

        stripped = _strip_jsonc_comments(raw)
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise CanonicalManifestRegistryError(
                f"Invalid JSONC payload in {path.name}: {exc}"
            ) from exc

        if not isinstance(payload, dict):
            raise CanonicalManifestRegistryError(
                f"{path.name}: top-level payload must be object"
            )

        payload = normalize_manifest_for_runtime(payload)
        _validate_minimum_shape(path.name, payload)
        return payload

    def _validate_schema_versions(self, manifests: dict[str, dict[str, Any]]) -> None:
        policy = self.schema_policy()
        mode = str(policy["mode"])
        active = {str(v) for v in policy["active_versions"]}
        deprecated = {str(v) for v in policy["deprecated_versions"]}
        allowed = active.union(deprecated)
        latest_active = _latest_version(list(active))

        deprecated_found: list[str] = []
        for filename, payload in manifests.items():
            version = payload.get("schema_version")
            if not isinstance(version, str) or not version.strip():
                raise CanonicalManifestRegistryError(
                    f"{filename}: schema_version must be a non-empty string"
                )
            _parse_version(version)

            if version not in allowed:
                raise CanonicalManifestRegistryError(
                    f"{filename}: schema_version '{version}' is not in schema policy "
                    f"(active={sorted(active)}, deprecated={sorted(deprecated)})"
                )

            if mode == "strict" and version in deprecated:
                raise CanonicalManifestRegistryError(
                    f"{filename}: schema_version '{version}' is deprecated "
                    "and disallowed in strict mode"
                )
            if mode == "latest_only" and version != latest_active:
                raise CanonicalManifestRegistryError(
                    f"{filename}: schema_version '{version}' is not latest "
                    f"active version '{latest_active}'"
                )
            if mode == "compat" and version in deprecated:
                deprecated_found.append(f"{filename}:{version}")

        if deprecated_found:
            # Non-fatal for compat mode; keep explicit signal in logs/validator output.
            # Stored on cache for script visibility without adding logger
            # dependency here.
            self._policy_cache = {
                **policy,
                "deprecated_found": deprecated_found,
            }


def _strip_jsonc_comments(text: str) -> str:
    out_lines: list[str] = []
    for line in text.splitlines():
        if line.lstrip().startswith("//"):
            continue
        cleaned = _JSONC_LINE_COMMENT_RE.sub(r"\1", line)
        out_lines.append(cleaned)
    return "\n".join(out_lines)


def _validate_minimum_shape(filename: str, payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise CanonicalManifestRegistryError(
            f"{filename}: top-level payload must be object"
        )

    required_top_level = {
        "schema_version",
        "session_id",
        "generated_at",
        "tenant",
        "tickets",
        "projects",
        "dashboard",
        "kpi",
        "hr_hub",
    }
    missing = sorted(required_top_level - set(payload.keys()))
    if missing:
        raise CanonicalManifestRegistryError(
            f"{filename}: missing required top-level keys: {', '.join(missing)}"
        )

    tenant = payload.get("tenant")
    if not isinstance(tenant, dict) or not tenant.get("industry"):
        raise CanonicalManifestRegistryError(f"{filename}: tenant.industry is required")

    for path in (
        "tickets.queues",
        "projects.projects",
        "dashboard.dashboards",
        "kpi.kpis",
        "hr_hub.request_types",
    ):
        parent, child = path.split(".")
        node = payload.get(parent)
        if not isinstance(node, dict) or not isinstance(node.get(child), list):
            raise CanonicalManifestRegistryError(f"{filename}: {path} must be a list")

    hr_hub = payload.get("hr_hub")
    if not isinstance(hr_hub, dict) or not isinstance(hr_hub.get("employees"), list):
        raise CanonicalManifestRegistryError(
            f"{filename}: hr_hub.employees must be a list"
        )


def _parse_version(raw: str) -> tuple[int, ...]:
    parts = raw.split(".")
    if not parts or any(not p.isdigit() for p in parts):
        raise CanonicalManifestRegistryError(
            f"Invalid schema version '{raw}'. Expected numeric dotted "
            "version like '2.0'"
        )
    return tuple(int(p) for p in parts)


def _latest_version(versions: list[str]) -> str:
    if not versions:
        raise CanonicalManifestRegistryError("No active schema versions configured")
    return max(versions, key=_parse_version)


def _normalize_versions(values: list[Any], field: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise CanonicalManifestRegistryError(
                f"schema_policy.{field} contains invalid version: {value!r}"
            )
        _parse_version(value)
        if value not in seen:
            out.append(value)
            seen.add(value)
    return out
