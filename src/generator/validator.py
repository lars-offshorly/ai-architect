from __future__ import annotations

from dataclasses import dataclass

from catalog.bundle_catalog import BundleCatalog, BundleDefinition

from .schemas import DummyDataJSON, GenerationJSON


class ValidationError(Exception):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


@dataclass(slots=True)
class ValidationResult:
    errors: list[str]


_LEGACY_RENDER_KEY_REQUIRED_MODULES: dict[str, tuple[str, ...]] = {
    "hr_hub": ("tickets", "queues", "kpis", "dashboard"),
}


def _bundle_candidates_for_key(
    bundle_key_or_render_key: str,
    catalog: BundleCatalog,
) -> list[BundleDefinition]:
    """Resolve candidate bundles from catalog key first, then render key."""
    direct = catalog.get(bundle_key_or_render_key)
    if direct is not None:
        return [direct]

    return [
        bundle
        for bundle in catalog.list_all()
        if bundle.render_key == bundle_key_or_render_key
    ]


def _validate_modules_against_bundle(
    generation: GenerationJSON,
    bundle: BundleDefinition,
) -> None:
    module_keys = [m.module_key for m in generation.modules]
    required_modules = list(bundle.default_modules)
    known_modules = set(bundle.default_modules) | set(bundle.optional_modules)

    legacy_required = _LEGACY_RENDER_KEY_REQUIRED_MODULES.get(generation.bundle)
    if (
        legacy_required is not None
        and generation.bundle == bundle.render_key
        and generation.bundle != bundle.bundle_key
    ):
        required_modules = list(legacy_required)
        known_modules = set(legacy_required)

    for required in required_modules:
        if required not in module_keys:
            raise ValidationError([f"Missing default module: {required}"])

    for key in module_keys:
        if key not in known_modules:
            raise ValidationError([f"Unknown module_key: {key}"])


def validate_generation_json(
    generation: GenerationJSON,
    catalog: BundleCatalog,
) -> None:
    bundles = _bundle_candidates_for_key(generation.bundle, catalog)
    if not bundles:
        raise ValidationError([f"Unknown bundle: {generation.bundle}"])

    last_error: ValidationError | None = None
    for bundle in bundles:
        try:
            _validate_modules_against_bundle(generation, bundle)
            return
        except ValidationError as exc:
            last_error = exc

    if last_error is not None:
        raise last_error


def validate_dummy_data_json(
    dummy_data: DummyDataJSON,
    generation: GenerationJSON,
) -> None:
    if dummy_data.bundle != generation.bundle:
        raise ValidationError(
            [
                (
                    "Bundle mismatch between generation and dummy data: "
                    f"{generation.bundle} != {dummy_data.bundle}"
                )
            ]
        )

    stores = dummy_data.stores.model_dump()
    for module in generation.modules:
        if not module.enabled:
            continue
        key = module.module_key
        if key == "dashboard":
            store_key = "dashboard_widgets"
        else:
            store_key = key
        value = stores.get(store_key)
        if isinstance(value, list) and len(value) == 0:
            raise ValidationError([f"Store '{store_key}' must not be empty"])


def validate_output(
    generation: GenerationJSON,
    dummy_data: DummyDataJSON,
    catalog: BundleCatalog,
) -> ValidationResult | None:
    try:
        validate_generation_json(generation, catalog)
        validate_dummy_data_json(dummy_data, generation)
    except ValidationError as exc:
        return ValidationResult(errors=exc.errors)
    return None
