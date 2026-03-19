from __future__ import annotations

from catalog.bundle_catalog import BundleCatalog

from .schemas import DummyDataJSON, GenerationJSON, ModuleConfig


MODULE_STORE_MAP: dict[str, str] = {
    "tickets": "tickets",
    "queues": "queues",
    "kpis": "kpis",
    "dashboard": "dashboard_widgets",
    "tasks": "tasks",
    "timelines": "tasks",
    "milestones": "milestones",
    "assets": "assets",
    "maintenance": "maintenance",
    "work_orders": "tasks",
    "scheduling": "tasks",
    "forms": "tasks",
}


class ValidationError(Exception):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors


def _enabled_module_keys(modules: list[ModuleConfig]) -> list[str]:
    return [module.module_key for module in modules if module.enabled]


def validate_generation_json(data: GenerationJSON, catalog: BundleCatalog) -> None:
    errors: list[str] = []
    bundle_definition = catalog.get(data.bundle)

    if bundle_definition is None:
        errors.append(f"Unknown bundle: {data.bundle}")

    if not data.session_id.strip():
        errors.append("session_id must not be empty")

    module_keys = {module.module_key for module in data.modules}
    if bundle_definition is not None:
        required_modules = set(bundle_definition.default_modules)
        missing_modules = sorted(required_modules - module_keys)
        if missing_modules:
            errors.append(
                f"Missing default module(s): {', '.join(missing_modules)}",
            )

        allowed_modules = set(bundle_definition.default_modules)
        allowed_modules.update(bundle_definition.optional_modules)
        unknown_modules = sorted(module_keys - allowed_modules)
        if unknown_modules:
            errors.append(f"Unknown module_key(s): {', '.join(unknown_modules)}")

    if errors:
        raise ValidationError(errors)


def validate_dummy_data_json(data: DummyDataJSON, generation: GenerationJSON) -> None:
    errors: list[str] = []

    if data.bundle != generation.bundle:
        errors.append(
            "Bundle mismatch between generation and dummy data: "
            f"{generation.bundle} != {data.bundle}",
        )

    if data.session_id != generation.session_id:
        errors.append(
            "session_id mismatch between generation and dummy data: "
            f"{generation.session_id} != {data.session_id}",
        )

    for module_key in _enabled_module_keys(generation.modules):
        store_key = MODULE_STORE_MAP.get(module_key)
        if store_key is None:
            continue

        store_items = getattr(data.stores, store_key)
        if not store_items:
            errors.append(
                f"Store '{store_key}' must contain at least one record when "
                f"module '{module_key}' is enabled",
            )

    if errors:
        raise ValidationError(errors)


def validate_output(
    generation: GenerationJSON,
    dummy_data: DummyDataJSON,
    catalog: BundleCatalog,
) -> ValidationError | None:
    errors: list[str] = []

    for validator in (
        lambda: validate_generation_json(generation, catalog),
        lambda: validate_dummy_data_json(dummy_data, generation),
    ):
        try:
            validator()
        except ValidationError as exc:
            errors.extend(exc.errors)

    if errors:
        return ValidationError(errors)

    return None
