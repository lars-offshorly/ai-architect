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


def validate_generation_json(
    generation: GenerationJSON,
    catalog: BundleCatalog,
) -> None:
    bundle = catalog.get(generation.bundle)
    if bundle is None:
        raise ValidationError([f"Unknown bundle: {generation.bundle}"])

    module_keys = [m.module_key for m in generation.modules]
    for required in bundle.default_modules:
        if required not in module_keys:
            raise ValidationError([f"Missing default module: {required}"])

    known_modules = set(bundle.default_modules) | set(bundle.optional_modules)
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
