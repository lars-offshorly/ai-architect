from __future__ import annotations

from dataclasses import dataclass

from catalog.bundle_catalog import BundleCatalog

from .schemas import DummyDataJSON, GenerationJSON


class ValidationError(Exception):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


@dataclass(slots=True)
class ValidationResult:
    errors: list[str]


_LEGACY_RENDER_MODULES: dict[str, set[str]] = {
    "hr_hub": {"tickets", "queues", "kpis", "dashboard"},
}


def validate_generation_json(
    generation: GenerationJSON,
    catalog: BundleCatalog,
) -> None:
    bundle = catalog.get(generation.bundle)
    using_render_key = False
    if bundle is None:
        bundle = next(
            (
                candidate
                for candidate in catalog.list_all()
                if candidate.render_key == generation.bundle
            ),
            None,
        )
        using_render_key = bundle is not None
    if bundle is None:
        raise ValidationError([f"Unknown bundle: {generation.bundle}"])

    required_modules = set(bundle.default_modules)
    known_modules = set(bundle.default_modules) | set(bundle.optional_modules)
    if using_render_key and generation.bundle in _LEGACY_RENDER_MODULES:
        required_modules = set(_LEGACY_RENDER_MODULES[generation.bundle])
        known_modules = set(_LEGACY_RENDER_MODULES[generation.bundle])

    module_keys = [m.module_key for m in generation.modules]
    for required in required_modules:
        if required not in module_keys:
            raise ValidationError([f"Missing default module: {required}"])

    for key in module_keys:
        if key not in known_modules:
            raise ValidationError([f"Unknown module_key: {key}"])


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
