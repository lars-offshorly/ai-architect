"""Legacy generator output validation helpers."""

from __future__ import annotations

from catalog.bundle_catalog import BundleCatalog

from .schemas import DummyDataJSON, GenerationJSON

_LEGACY_BUNDLE_MODULES: dict[str, set[str]] = {
    "hr_hub": {"tickets", "queues", "kpis", "dashboard"},
}

_LEGACY_BUNDLE_ALIASES: dict[str, str] = {
    "hr_hub": "hr_management",
}


class ValidationError(ValueError):
    """Raised when legacy generator output is structurally invalid."""


def validate_generation_json(
    generation: GenerationJSON,
    catalog: BundleCatalog,
) -> None:
    bundle = catalog.get(generation.bundle)
    if bundle is None:
        alias = _LEGACY_BUNDLE_ALIASES.get(generation.bundle)
        bundle = catalog.get(alias) if alias is not None else None
    if bundle is None:
        raise ValidationError(f"Unknown bundle: {generation.bundle}")

    module_keys = {module.module_key for module in generation.modules}
    default_modules = _LEGACY_BUNDLE_MODULES.get(
        generation.bundle,
        set(bundle.default_modules),
    )
    allowed_modules = default_modules | set(bundle.optional_modules)
    unknown_modules = module_keys - allowed_modules
    if unknown_modules:
        unknown = ", ".join(sorted(unknown_modules))
        raise ValidationError(f"Unknown module_key: {unknown}")

    missing_modules = default_modules - module_keys
    if missing_modules:
        missing = ", ".join(sorted(missing_modules))
        raise ValidationError(f"Missing default module: {missing}")


def validate_dummy_data_json(
    dummy_data: DummyDataJSON,
    generation: GenerationJSON,
) -> None:
    if dummy_data.bundle != generation.bundle:
        raise ValidationError(
            f"Bundle mismatch: {dummy_data.bundle} != {generation.bundle}"
        )

    stores = dummy_data.stores
    for store_name in ("tickets", "queues", "kpis", "dashboard_widgets"):
        values = getattr(stores, store_name)
        if not values:
            raise ValidationError(f"Store '{store_name}' must not be empty")


def validate_output(
    generation: GenerationJSON,
    dummy_data: DummyDataJSON,
    catalog: BundleCatalog,
) -> ValidationError | None:
    try:
        validate_generation_json(generation, catalog)
        validate_dummy_data_json(dummy_data, generation)
    except ValidationError as exc:
        return exc
    return None
