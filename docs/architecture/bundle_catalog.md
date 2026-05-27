# Bundle Catalog (Canonical Manifests)

## Runtime Source of Truth

Bundle and store data is now loaded from canonical JSONC manifests under `new_json_samples/*.jsonc`.

- Primary loader: `CanonicalManifestRegistry`
- Runtime entrypoint: `RegistryFacade`
- Industry routing map: `new_json_samples/industry_bundle_map.json`

`src/templates/bundle_registry.yaml` is not the primary runtime source for bundle resolution/metadata/store composition.

## How Routing Works

1. `CanonicalManifestRegistry` loads all `.jsonc` files in `new_json_samples`.
2. `CanonicalBundleResolver` matches request signals to an industry.
Signal sources:
- explicit industry token match
- aliases from `industry_bundle_map.json`
3. The resolver maps industry -> `bundle_key` from the mapping file.
4. `RegistryFacade` is used by runtime flows.
Facade operations:
- resolve bundle
- build payload stores
- return bundle metadata
- list supported bundles

## Strict Mode and Fallback

- `CANONICAL_STRICT_INDUSTRY_MAPPING=true` (default): unknown or unmapped industries fail fast.
- `CANONICAL_STRICT_INDUSTRY_MAPPING=false`: unknown industry can fall back to `generic`.
- `CANONICAL_ALLOW_REGISTRY_MODULE_FALLBACK=false` (default): no module fallback from legacy registry.

## Add a New JSONC Manifest

To onboard a new canonical manifest:

1. Add the new file to `new_json_samples/` with extension `.jsonc`.
2. Ensure required top-level keys exist.
Required top-level keys:
- `schema_version`
- `session_id`
- `generated_at`
- `tenant` (must include `tenant.industry`)
- `tickets`
- `projects`
- `dashboard`
- `kpi`
- `hr_hub`
3. Ensure required list shapes exist.
Required list shapes:
- `tickets.queues`
- `projects.projects`
- `dashboard.dashboards`
- `kpi.kpis`
- `hr_hub.request_types`
- `hr_hub.employees`
4. Add or update mapping in `new_json_samples/industry_bundle_map.json`.
Mapping requirements:
- add `mappings.<industry>.bundle_key`
- optionally add `mappings.<industry>.aliases`
5. Run validation:

```bash
PYTHONPATH=. python scripts/validate_canonical_manifests.py
```

If strict mode is enabled, missing mapping coverage will fail validation.

## Auto-Load Behavior

- New `.jsonc` files are auto-discovered from `new_json_samples` at runtime.
- Auto-discovery does not imply routable. Routing requires a valid industry mapping entry (in strict mode).
- In non-strict mode only, unmatched requests may resolve to `generic`.

## Transitional Note

Legacy files remain on disk temporarily for compatibility and phased cleanup, but canonical manifests are the authoritative runtime contract.
