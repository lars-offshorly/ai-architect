from __future__ import annotations

# pylint: disable=duplicate-code
from pathlib import Path

from agents.interpreter.missing_fields import MissingFieldDetector
from catalog.bundle_catalog import BundleCatalog
from domain.enums.missing_field_type import MissingFieldType
from domain.models.extraction_result import ClassificationSignals, ExtractionResult

REGISTRY_PATH = (
    Path(__file__).resolve().parents[3] / "src/templates/bundle_registry.yaml"
)


def _detector() -> MissingFieldDetector:
    catalog = BundleCatalog(REGISTRY_PATH)
    required_slots = {
        bundle.bundle_key: bundle.required_slots for bundle in catalog.list_all()
    }
    return MissingFieldDetector(catalog, required_slots)


def test_compute_includes_generic_critical_fields_when_no_signals() -> None:
    detector = _detector()
    extracted = ExtractionResult(session_id="s1")

    missing = detector.compute(extracted, bundle_key="hr_management")

    assert MissingFieldType.PRIMARY_USE_CASE in missing
    assert MissingFieldType.ENTITY_TYPE in missing


def test_compute_includes_workflow_type_when_required_signals_do_not_overlap() -> None:
    detector = _detector()
    extracted = ExtractionResult(
        session_id="s1",
        classification_signals=ClassificationSignals(
            keywords=["calendar"], entities=["room"], intents=["book meeting"]
        ),
    )

    missing = detector.compute(extracted, bundle_key="hr_management")

    assert MissingFieldType.WORKFLOW_TYPE in missing


def test_compute_omits_workflow_type_when_required_signal_overlaps() -> None:
    detector = _detector()
    extracted = ExtractionResult(
        session_id="s1",
        classification_signals=ClassificationSignals(
            keywords=["leave management"],
            entities=["employee"],
            intents=["handle leave requests"],
            workflow_hints=["employee leave workflow"],
        ),
    )

    missing = detector.compute(extracted, bundle_key="hr_management")

    assert MissingFieldType.WORKFLOW_TYPE not in missing


def test_compute_only_checks_supported_enum_slots() -> None:
    detector = _detector()
    extracted = ExtractionResult(
        session_id="s1",
        classification_signals=ClassificationSignals(
            workflow_hints=["employee onboarding"],
            entities=["employee"],
        ),
    )

    missing = detector.compute(extracted, bundle_key="ticketing")

    assert MissingFieldType.COMPANY_NAME not in missing
    assert MissingFieldType.TEAM_SIZE not in missing


def test_compute_is_deduped_and_enum_ordered() -> None:
    detector = _detector()
    extracted = ExtractionResult(session_id="s1")

    missing = detector.compute(extracted, bundle_key="hr_management")

    assert missing == sorted(
        set(missing),
        key=lambda field: list(MissingFieldType).index(field),
    )
