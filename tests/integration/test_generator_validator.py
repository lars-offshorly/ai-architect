from __future__ import annotations

import pytest
from generator.schemas import (
    DummyDataJSON,
    GenerationJSON,
    ModuleConfig,
    StoreData,
    WorkspaceMeta,
)
from generator.validator import (
    ValidationError,
    validate_dummy_data_json,
    validate_generation_json,
    validate_output,
)

from catalog.bundle_catalog import BundleCatalog


@pytest.fixture(name="catalog")
def fixture_catalog(shared_catalog: BundleCatalog) -> BundleCatalog:
    return shared_catalog


def _valid_generation() -> GenerationJSON:
    return GenerationJSON(
        schema_version="1.0",
        session_id="session-123",
        bundle="hr_hub",
        entity_type="people",
        modules=[
            ModuleConfig(module_key="tickets", enabled=True, config={}),
            ModuleConfig(module_key="queues", enabled=True, config={}),
            ModuleConfig(module_key="kpis", enabled=True, config={}),
            ModuleConfig(module_key="dashboard", enabled=True, config={}),
        ],
        workspace_meta=WorkspaceMeta(
            team_size=12,
            industry_hint="tech_agency",
            generated_at="2026-02-25T11:00:00+08:00",
        ),
    )


def _valid_dummy_data() -> DummyDataJSON:
    return DummyDataJSON(
        schema_version="1.0",
        session_id="session-123",
        bundle="hr_hub",
        stores=StoreData(
            tickets=[{"id": 1, "title": "ticket"}],
            queues=[{"id": 1, "name": "queue"}],
            kpis=[{"label": "kpi"}],
            dashboard_widgets=[{"widget": "summary"}],
        ),
    )


def test_validate_generation_json_passes(catalog: BundleCatalog) -> None:
    validate_generation_json(_valid_generation(), catalog)


def test_validate_generation_json_fails_unknown_bundle(catalog: BundleCatalog) -> None:
    generation = _valid_generation().model_copy(update={"bundle": "unknown"})

    with pytest.raises(ValidationError, match="Unknown bundle"):
        validate_generation_json(generation, catalog)


def test_validate_generation_json_fails_missing_default_module(
    catalog: BundleCatalog,
) -> None:
    generation = _valid_generation().model_copy(
        update={
            "modules": [
                ModuleConfig(module_key="tickets", enabled=True, config={}),
                ModuleConfig(module_key="queues", enabled=True, config={}),
                ModuleConfig(module_key="kpis", enabled=True, config={}),
            ],
        },
    )

    with pytest.raises(ValidationError, match="Missing default module"):
        validate_generation_json(generation, catalog)


def test_validate_generation_json_fails_unknown_module_key(
    catalog: BundleCatalog,
) -> None:
    generation = _valid_generation().model_copy(
        update={
            "modules": [
                *_valid_generation().modules,
                ModuleConfig(module_key="unknown_module", enabled=True, config={}),
            ],
        },
    )

    with pytest.raises(ValidationError, match="Unknown module_key"):
        validate_generation_json(generation, catalog)


def test_validate_dummy_data_json_fails_bundle_mismatch() -> None:
    generation = _valid_generation()
    dummy_data = _valid_dummy_data().model_copy(update={"bundle": "generic"})

    with pytest.raises(ValidationError, match="Bundle mismatch"):
        validate_dummy_data_json(dummy_data, generation)


def test_validate_dummy_data_json_fails_empty_tickets_store() -> None:
    generation = _valid_generation()
    dummy_data = _valid_dummy_data().model_copy(
        update={
            "stores": StoreData(
                tickets=[],
                queues=[{"id": 1, "name": "queue"}],
                kpis=[{"label": "kpi"}],
                dashboard_widgets=[{"widget": "summary"}],
            ),
        },
    )

    with pytest.raises(ValidationError, match="Store 'tickets'"):
        validate_dummy_data_json(dummy_data, generation)


def test_validate_output_returns_none_for_valid_payload(
    catalog: BundleCatalog,
) -> None:
    error = validate_output(
        generation=_valid_generation(),
        dummy_data=_valid_dummy_data(),
        catalog=catalog,
    )

    assert error is None
