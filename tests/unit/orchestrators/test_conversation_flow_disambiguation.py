from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from domain.models.bundle import BundleSuggestion
from domain.models.classification_result import ClassificationResult
from domain.models.conversation import ConversationMessage
from domain.models.extraction_result import ExtractionResult
from domain.models.session import Session
from orchestrators.conversation_flow import ConversationFlow, ConversationTurnRequest


class _FakeRegistryFacade:
    def industry_bundle_map(self) -> dict[str, dict[str, object]]:
        return {
            "bpo_contact_center": {
                "bundle_key": "ticketing",
                "aliases": [
                    "call center",
                    "customer support",
                    "help desk",
                    "service desk",
                ],
            },
            "construction_firm": {
                "bundle_key": "construction",
                "aliases": [
                    "contractor",
                    "construction",
                    "subcontractor",
                    "jobsite",
                ],
            },
            "hr_recruitment_agency": {
                "bundle_key": "hr_management",
                "aliases": ["recruitment", "staffing", "talent", "payroll"],
            },
        }

    def inferred_modules_for_bundle(self, _bundle_key: str) -> list[str]:
        return []


def _make_flow(
    classification_status: str = "proceed",
) -> tuple[ConversationFlow, MagicMock, MagicMock]:
    interpreter = MagicMock()
    interpreter.summarize_history = AsyncMock(return_value="")
    interpreter.extract_only = AsyncMock(return_value=ExtractionResult(session_id="s1"))
    interpreter.interpret = AsyncMock(
        return_value=(
            ExtractionResult(session_id="s1"),
            ClassificationResult(
                session_id="s1",
                selected_bundle=BundleSuggestion(
                    bundle_key="construction",
                    display_name="Construction",
                    confidence=0.9,
                    reasoning="high",
                    matched_signals=[],
                ),
                ranked_candidates=[],
                confidence_status=classification_status,
                top_confidence=0.9,
                score_gap=0.5,
                missing_context=[],
                reasoning="ok",
            ),
        )
    )
    interpreter.top_bundle = MagicMock(
        return_value=BundleSuggestion(
            bundle_key="construction",
            display_name="Construction",
            confidence=0.9,
            reasoning="high",
            matched_signals=[],
        )
    )
    replier = MagicMock()
    replier.build_clarification = AsyncMock(return_value=(None, ""))
    replier.build_bundle_suggestion = AsyncMock(return_value="Bundle suggestion body")
    flow = ConversationFlow(
        interpreter_service=interpreter,
        replier_service=replier,
        required_slots_by_bundle={},
        registry_facade=_FakeRegistryFacade(),  # type: ignore[arg-type]
    )
    return flow, interpreter, replier


@pytest.mark.asyncio
async def test_asks_industry_disambiguation_when_multiple_industries_match() -> None:
    # The classifier itself is uncertain ("clarify") AND multiple industries
    # have strong alias hits in the message: that is the only case where the
    # disambiguation question should fire.
    flow, _interpreter, _replier = _make_flow(classification_status="clarify")
    session = Session(session_id="s1", clarification_turn_count=1)
    msg = (
        "We have contractor and subcontractor workflows on every jobsite, "
        "and we also run a call center and help desk for customer support."
    )

    result = await flow.process_turn(
        ConversationTurnRequest(
            session_id="s1",
            user_message=msg,
            history=[ConversationMessage(role="user", content=msg)],
            session=session,
        )
    )

    assert result["status"] == "awaiting_input"
    assert "which best describes your business" in str(result["question"]).lower()


@pytest.mark.asyncio
async def test_skips_disambiguation_when_resolver_is_confident() -> None:
    # Even with alias hits for multiple industries, a confident classifier
    # ("proceed") should suppress the disambiguation question.
    flow, _interpreter, _replier = _make_flow(classification_status="proceed")
    session = Session(session_id="s1", clarification_turn_count=1)
    msg = "We run a BPO contact center with a call center and 280 employees"

    result = await flow.process_turn(
        ConversationTurnRequest(
            session_id="s1",
            user_message=msg,
            history=[ConversationMessage(role="user", content=msg)],
            session=session,
        )
    )

    # Should NOT be the disambiguation question; flow continues to next step.
    assert (
        "which best describes your business"
        not in str(result.get("question", "")).lower()
    )


@pytest.mark.asyncio
async def test_persists_context_and_confirmation_summary() -> None:
    flow, _interpreter, _replier = _make_flow()
    session = Session(session_id="s1", clarification_turn_count=1, confirmed=False)
    msg = "Im from PH, I own a construction company called Offshorly and I need a 5 people ticketing website"

    result = await flow.process_turn(
        ConversationTurnRequest(
            session_id="s1",
            user_message=msg,
            history=[ConversationMessage(role="user", content=msg)],
            session=session,
        )
    )

    assert session.company_industry_claim == "construction_firm"
    assert session.preselected_bundle_key == "construction"
    assert session.primary_workflow == "ticketing"
    assert session.inferred_region == "PH"
    assert session.inferred_team_size == 5
    assert session.inferred_company_name == "Offshorly"
    assert result["status"] == "pending_confirmation"
    assert "Industry: construction" in str(result["selection_context"])
    assert "Workflow: ticketing" in str(result["selection_context"])
    assert "Industry: construction" not in str(result["message"])
