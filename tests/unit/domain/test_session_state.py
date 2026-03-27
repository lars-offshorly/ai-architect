from __future__ import annotations

from domain.models.session import Session


class TestSessionPipelineStateFields:
    def test_session_defaults_pipeline_fields_to_none_and_zero(self) -> None:
        session = Session()

        assert session.accumulated_extraction is None
        assert session.latest_classification is None
        assert session.latest_recommendation is None
        assert session.clarification_turn_count == 0

    def test_session_accepts_accumulated_extraction(self) -> None:
        payload = {"keywords": ["hr", "leave"], "entities": ["employee"]}
        session = Session(accumulated_extraction=payload)

        assert session.accumulated_extraction == payload

    def test_session_accepts_latest_classification(self) -> None:
        payload = {"confidence_status": "clarify", "top_bundle_key": None}
        session = Session(latest_classification=payload)

        assert session.latest_classification == payload

    def test_session_accepts_latest_recommendation(self) -> None:
        payload = {"primary_bundle": "hr_management", "fallback_bundles": []}
        session = Session(latest_recommendation=payload)

        assert session.latest_recommendation == payload

    def test_session_accepts_clarification_turn_count(self) -> None:
        session = Session(clarification_turn_count=2)

        assert session.clarification_turn_count == 2

    def test_existing_session_fields_unaffected(self) -> None:
        session = Session(
            user_id="user-123",
            confirmed=True,
            selected_bundle_key="hr_management",
            turn_count=3,
        )

        assert session.user_id == "user-123"
        assert session.confirmed is True
        assert session.selected_bundle_key == "hr_management"
        assert session.turn_count == 3
        assert session.clarification_turn_count == 0
