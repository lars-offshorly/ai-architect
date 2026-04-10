from __future__ import annotations

from dataclasses import dataclass

import pytest

from agents.app_generator.service import AppGeneratorService
from core.exceptions import InvalidPayloadError


@dataclass
class _FakeBundle:
    template_dir: str
    render_key: str
    default_modules: list[str]


class _FakeCatalog:
    def __init__(self, bundles: dict[str, _FakeBundle]) -> None:
        self._bundles = bundles

    def get(self, bundle_key: str) -> _FakeBundle | None:
        return self._bundles.get(bundle_key)


class _FakeTemplateRepo:
    def __init__(self, templates: dict[str, dict[str, object]]) -> None:
        self._templates = templates

    def load_app_json(self, bundle_key: str) -> dict[str, object]:
        return dict(self._templates[bundle_key])


def test_assemble_injects_modules_when_template_omits_them() -> None:
    svc = AppGeneratorService(
        template_repo=_FakeTemplateRepo(
            {
                "field_service": {
                    "schema_version": "1.0",
                    "bundle_key": "ticketing",
                    "config": {
                        "work_order_statuses": ["open"],
                        "work_order_priorities": ["high"],
                        "service_types": ["incident"],
                        "kpi_definitions": [
                            {
                                "key": "avg_resolution_time",
                                "label": "Average Resolution Time",
                                "unit": "duration",
                            }
                        ],
                    },
                }
            }
        ),
        catalog=_FakeCatalog(
            {
                "ticketing": _FakeBundle(
                    template_dir="field_service",
                    render_key="ticketing",
                    default_modules=["tickets", "dashboard", "kpi"],
                )
            }
        ),
    )

    payload = svc.assemble(
        session_id="test-session",
        bundle_key="ticketing",
        display_name="Ticketing Tool",
        dummy_data={"bundle_key": "ticketing", "stores": {}, "session_id": "test-session"},
    )

    assert payload.modules == ["tickets", "dashboard", "kpi"]
    assert payload.generation_json["modules"] == ["tickets", "dashboard", "kpi"]


def test_assemble_validates_generation_json_with_render_key() -> None:
    svc = AppGeneratorService(
        template_repo=_FakeTemplateRepo(
            {
                "hr_hub": {
                    "schema_version": "1.0",
                    "bundle_key": "hr_hub",
                    "config": {
                        "ticket_categories": ["leave"],
                        "default_statuses": ["open"],
                        "default_priorities": ["high"],
                        "queue_names": ["HR Requests"],
                        "kpi_definitions": [
                            {
                                "key": "active_headcount",
                                "label": "Active Headcount",
                                "unit": "count",
                            }
                        ],
                    },
                }
            }
        ),
        catalog=_FakeCatalog(
            {
                "hr_management": _FakeBundle(
                    template_dir="hr_hub",
                    render_key="hr_hub",
                    default_modules=["hr_hub"],
                )
            }
        ),
    )

    payload = svc.assemble(
        session_id="test-session",
        bundle_key="hr_management",
        display_name="HR Management",
        dummy_data={"bundle_key": "hr_hub", "stores": {}, "session_id": "test-session"},
    )

    assert payload.bundle_key == "hr_hub"
    assert payload.generation_json["bundle_key"] == "hr_hub"


def test_assemble_adds_missing_kpi_ids_to_dummy_data() -> None:
    svc = AppGeneratorService(
        template_repo=_FakeTemplateRepo(
            {
                "field_service": {
                    "schema_version": "1.0",
                    "bundle_key": "ticketing",
                    "config": {
                        "work_order_statuses": ["open"],
                        "work_order_priorities": ["high"],
                        "service_types": ["incident"],
                        "kpi_definitions": [
                            {
                                "key": "avg_resolution_time",
                                "label": "Average Resolution Time",
                                "unit": "duration",
                            }
                        ],
                    },
                }
            }
        ),
        catalog=_FakeCatalog(
            {
                "ticketing": _FakeBundle(
                    template_dir="field_service",
                    render_key="ticketing",
                    default_modules=["tickets", "dashboard", "kpi"],
                )
            }
        ),
    )

    payload = svc.assemble(
        session_id="test-session",
        bundle_key="ticketing",
        display_name="Ticketing Tool",
        dummy_data={
            "bundle_key": "ticketing",
            "stores": {
                "kpis": [
                    {
                        "key": "avg_resolution_time",
                        "label": "Avg. Resolution Time",
                        "type": "duration",
                        "source_service": "tickets",
                        "sample_value": 3.2,
                    }
                ]
            },
            "session_id": "test-session",
        },
    )

    kpis = payload.dummy_data_json.get("stores", {}).get("kpis", [])
    assert isinstance(kpis, list)
    assert isinstance(kpis[0], dict)
    assert kpis[0]["id"] == "avg_resolution_time"


def test_assemble_raises_on_dummy_data_bundle_key_mismatch() -> None:
    svc = AppGeneratorService(
        template_repo=_FakeTemplateRepo(
            {
                "field_service": {
                    "schema_version": "1.0",
                    "bundle_key": "ticketing",
                    "config": {
                        "work_order_statuses": ["open"],
                        "work_order_priorities": ["high"],
                        "service_types": ["incident"],
                        "kpi_definitions": [
                            {
                                "key": "avg_resolution_time",
                                "label": "Average Resolution Time",
                                "unit": "duration",
                            }
                        ],
                    },
                }
            }
        ),
        catalog=_FakeCatalog(
            {
                "ticketing": _FakeBundle(
                    template_dir="field_service",
                    render_key="ticketing",
                    default_modules=["tickets", "dashboard", "kpi"],
                )
            }
        ),
    )

    with pytest.raises(InvalidPayloadError, match="bundle_key mismatch"):
        svc.assemble(
            session_id="test-session",
            bundle_key="ticketing",
            display_name="Ticketing Tool",
            dummy_data={
                "bundle_key": "hr_hub",
                "stores": {},
                "session_id": "test-session",
            },
        )
