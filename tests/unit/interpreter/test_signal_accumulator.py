from __future__ import annotations

# pylint: disable=no-member
from agents.interpreter.signal_accumulator import SignalAccumulator
from domain.enums.missing_field_type import MissingFieldType
from domain.models.extraction_result import (
    ClassificationSignals,
    ExtractionResult,
    PersonalizationSignals,
)


class TestSignalAccumulatorMerge:
    def test_merge_with_none_base_returns_current(self) -> None:
        current = ExtractionResult(
            session_id="s1",
            classification_signals=ClassificationSignals(keywords=["hr"]),
        )
        result = SignalAccumulator.merge(None, current)
        assert result.classification_signals.keywords == ["hr"]
        assert result.session_id == "s1"

    def test_merge_unions_keywords(self) -> None:
        base = ExtractionResult(
            session_id="s1",
            classification_signals=ClassificationSignals(keywords=["hr", "leave"]),
        )
        current = ExtractionResult(
            session_id="s1",
            classification_signals=ClassificationSignals(
                keywords=["leave", "employee"]
            ),
        )
        result = SignalAccumulator.merge(base, current)
        assert set(result.classification_signals.keywords) == {
            "hr",
            "leave",
            "employee",
        }

    def test_merge_unions_entities(self) -> None:
        base = ExtractionResult(
            session_id="s1",
            classification_signals=ClassificationSignals(entities=["employee"]),
        )
        current = ExtractionResult(
            session_id="s1",
            classification_signals=ClassificationSignals(entities=["manager"]),
        )
        result = SignalAccumulator.merge(base, current)
        assert set(result.classification_signals.entities) == {"employee", "manager"}

    def test_merge_unions_intents(self) -> None:
        base = ExtractionResult(
            session_id="s1",
            classification_signals=ClassificationSignals(intents=["request leave"]),
        )
        current = ExtractionResult(
            session_id="s1",
            classification_signals=ClassificationSignals(intents=["approve leave"]),
        )
        result = SignalAccumulator.merge(base, current)
        assert "request leave" in result.classification_signals.intents
        assert "approve leave" in result.classification_signals.intents

    def test_merge_unions_workflow_and_domain_hints(self) -> None:
        base = ExtractionResult(
            session_id="s1",
            classification_signals=ClassificationSignals(
                workflow_hints=["leave tracking"],
                domain_hints=["hr"],
            ),
        )
        current = ExtractionResult(
            session_id="s1",
            classification_signals=ClassificationSignals(
                workflow_hints=["attendance management"],
                domain_hints=["healthcare"],
            ),
        )
        result = SignalAccumulator.merge(base, current)
        assert "leave tracking" in result.classification_signals.workflow_hints
        assert "attendance management" in result.classification_signals.workflow_hints
        assert "hr" in result.classification_signals.domain_hints
        assert "healthcare" in result.classification_signals.domain_hints

    def test_merge_personalization_overwrites_with_current(self) -> None:
        base = ExtractionResult(
            session_id="s1",
            personalization_signals=PersonalizationSignals(company_name="OldCorp"),
        )
        current = ExtractionResult(
            session_id="s1",
            personalization_signals=PersonalizationSignals(company_name="NewCorp"),
        )
        result = SignalAccumulator.merge(base, current)
        assert result.personalization_signals.company_name == "NewCorp"

    def test_merge_personalization_keeps_base_when_current_is_none(self) -> None:
        base = ExtractionResult(
            session_id="s1",
            personalization_signals=PersonalizationSignals(company_name="Acme"),
        )
        current = ExtractionResult(
            session_id="s1",
            personalization_signals=PersonalizationSignals(company_name=None),
        )
        result = SignalAccumulator.merge(base, current)
        assert result.personalization_signals.company_name == "Acme"

    def test_merge_employee_names_unioned(self) -> None:
        base = ExtractionResult(
            session_id="s1",
            personalization_signals=PersonalizationSignals(employee_names=["Alice"]),
        )
        current = ExtractionResult(
            session_id="s1",
            personalization_signals=PersonalizationSignals(employee_names=["Bob"]),
        )
        result = SignalAccumulator.merge(base, current)
        assert set(result.personalization_signals.employee_names) == {"Alice", "Bob"}

    def test_merge_uses_current_missing_fields(self) -> None:
        base = ExtractionResult(
            session_id="s1",
            missing_fields=[MissingFieldType.TEAM_SIZE],
        )
        current = ExtractionResult(
            session_id="s1",
            missing_fields=[MissingFieldType.PRIMARY_USE_CASE],
        )
        result = SignalAccumulator.merge(base, current)
        assert result.missing_fields == [MissingFieldType.PRIMARY_USE_CASE]

    def test_merge_preserves_variant_key_from_latest_turn(self) -> None:
        base = ExtractionResult(
            session_id="s1",
            bundle_variant_key="app-01",
        )
        current = ExtractionResult(
            session_id="s1",
            bundle_variant_key="app-02",
        )
        result = SignalAccumulator.merge(base, current)
        assert result.bundle_variant_key == "app-02"

    def test_merge_preserves_session_id_from_current(self) -> None:
        base = ExtractionResult(session_id="old-session")
        current = ExtractionResult(session_id="new-session")
        result = SignalAccumulator.merge(base, current)
        assert result.session_id == "new-session"

    def test_merge_does_not_mutate_base(self) -> None:
        base = ExtractionResult(
            session_id="s1",
            classification_signals=ClassificationSignals(keywords=["hr"]),
        )
        current = ExtractionResult(
            session_id="s1",
            classification_signals=ClassificationSignals(keywords=["leave"]),
        )
        SignalAccumulator.merge(base, current)
        assert base.classification_signals.keywords == ["hr"]
