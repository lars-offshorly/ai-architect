"""Regression test for the BPO sample conversation.

Replays the opening of the sample from PARALLEL_WORK_SPLIT.md / the user's
report: a single rich first message describing a Manila BPO contact center
with 280 employees. With Phase 1-5 fixes in place, the flow should NOT keep
asking irrelevant follow-ups; it should reach pending_confirmation (or
ready_for_preview) within at most 2 turns.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from domain.models.bundle import BundleSuggestion
from domain.models.classification_result import ClassificationResult
from domain.models.conversation import ConversationMessage
from domain.models.extraction_result import (
    ClassificationSignals,
    ExtractionResult,
    PersonalizationSignals,
)
from domain.models.session import Session
from orchestrators.conversation_flow import (
    ConversationFlow,
    ConversationTurnRequest,
)


class _FakeRegistryFacade:
    def industry_bundle_map(self) -> dict[str, dict[str, object]]:
        return {
            "bpo_contact_center": {
                "bundle_key": "ticketing",
                "aliases": [
                    "bpo",
                    "contact center",
                    "call center",
                    "customer support",
                    "help desk",
                    "service desk",
                ],
            },
            "construction_firm": {
                "bundle_key": "construction",
                "aliases": [
                    "construction",
                    "contractor",
                    "subcontractor",
                    "jobsite",
                ],
            },
            "hr_recruitment_agency": {
                "bundle_key": "hr_management",
                "aliases": [
                    "recruitment",
                    "hiring agency",
                    "talent",
                    "payroll",
                    "employees",
                ],
            },
        }

    def inferred_modules_for_bundle(self, _bundle_key: str) -> list[str]:
        return ["tickets", "kpi", "dashboard"]


def _bpo_extraction(session_id: str) -> ExtractionResult:
    return ExtractionResult(
        session_id=session_id,
        classification_signals=ClassificationSignals(
            keywords=["customer care", "billing", "technical support", "queues"],
            entities=["agent", "queue", "ticket"],
            intents=["manage tickets"],
            workflow_hints=["ticket queue management"],
            domain_hints=["bpo"],
            metrics=["qa score"],
        ),
        personalization_signals=PersonalizationSignals(
            company_name="Nexora Connect",
        ),
    )


def _make_flow() -> tuple[ConversationFlow, MagicMock, MagicMock]:
    interpreter = MagicMock()
    interpreter.summarize_history = AsyncMock(return_value="")
    interpreter.extract_only = AsyncMock(
        return_value=_bpo_extraction("bpo-session")
    )
    interpreter.interpret = AsyncMock(
        return_value=(
            _bpo_extraction("bpo-session"),
            ClassificationResult(
                session_id="bpo-session",
                selected_bundle=BundleSuggestion(
                    bundle_key="ticketing",
                    display_name="Ticketing",
                    confidence=0.92,
                    reasoning="strong BPO signals",
                    matched_signals=["bpo", "contact center", "queue"],
                ),
                ranked_candidates=[
                    BundleSuggestion(
                        bundle_key="ticketing",
                        display_name="Ticketing",
                        confidence=0.92,
                        reasoning="strong",
                        matched_signals=[],
                    )
                ],
                confidence_status="proceed",
                top_confidence=0.92,
                score_gap=0.5,
                missing_context=[],
                reasoning="ok",
            ),
        )
    )
    interpreter.top_bundle = MagicMock(
        return_value=BundleSuggestion(
            bundle_key="ticketing",
            display_name="Ticketing",
            confidence=0.92,
            reasoning="strong",
            matched_signals=[],
        )
    )

    replier = MagicMock()
    replier.build_clarification = AsyncMock(return_value=(None, ""))
    replier.build_bundle_verification_question = AsyncMock(return_value="")
    replier.build_bundle_suggestion = AsyncMock(
        return_value=(
            "Setting up your contact center workspace for Nexora Connect with "
            "queues for customer care, billing, and technical support."
        )
    )

    flow = ConversationFlow(
        interpreter_service=interpreter,
        replier_service=replier,
        required_slots_by_bundle={},
        registry_facade=_FakeRegistryFacade(),  # type: ignore[arg-type]
    )
    return flow, interpreter, replier


@pytest.mark.asyncio
async def test_bpo_first_message_reaches_confirmation_in_one_turn() -> None:
    """The whole first user message contains industry + company + size + region.

    The flow should NOT ask a disambiguation question, NOT ask a verification
    question, and NOT keep clarifying. It should propose the bundle on turn 1.
    """
    flow, _interpreter, replier = _make_flow()
    session = Session(session_id="bpo-session")
    msg = (
        "We run a BPO contact center in Manila called Nexora Connect. "
        "We need customer care, billing, and technical support queues with "
        "QA dashboards for 280 employees."
    )

    result = await flow.process_turn(
        ConversationTurnRequest(
            session_id="bpo-session",
            user_message=msg,
            history=[ConversationMessage(role="user", content=msg)],
            session=session,
        )
    )

    # Should NOT trigger the disambiguation question.
    assert (
        "which best describes your business"
        not in str(result.get("question", "")).lower()
    )
    # Should reach a bundle proposal on turn 1.
    assert result["status"] == "pending_confirmation"
    # The replier should have produced a bundle suggestion, not a clarification.
    replier.build_bundle_suggestion.assert_awaited_once()


@pytest.mark.asyncio
async def test_bpo_session_signals_are_inferred_on_turn_one() -> None:
    """Verify the session picks up industry, region, company name, team size."""
    flow, _interpreter, _replier = _make_flow()
    session = Session(session_id="bpo-session")
    msg = (
        "We run a BPO contact center in Manila called Nexora Connect. "
        "We need customer care, billing, and technical support queues with "
        "QA dashboards for 280 employees."
    )

    await flow.process_turn(
        ConversationTurnRequest(
            session_id="bpo-session",
            user_message=msg,
            history=[ConversationMessage(role="user", content=msg)],
            session=session,
        )
    )

    assert session.company_industry_claim == "bpo_contact_center"
    assert session.preselected_bundle_key == "ticketing"
    assert session.inferred_region == "PH"
    assert session.inferred_team_size == 280
    assert session.inferred_company_name == "Nexora Connect"


@pytest.mark.asyncio
async def test_construction_company_named_extraction() -> None:
    """Regression: 'construction company named Equip' should infer the name.

    Previously the regex only matched 'called X', so 'named X' phrasings
    fell through, readiness stayed unmet, and the system kept asking for
    the company name.
    """
    from orchestrators.conversation_flow import _extract_company_name

    msg = (
        "Im from PH and I have construction company named Equip. "
        "I need a ticketing website for 5 employees please"
    )
    assert _extract_company_name(msg) == "Equip"


@pytest.mark.asyncio
async def test_bpo_confirmation_after_pending_completes_in_two_turns() -> None:
    """Turn 1 proposes, turn 2 user confirms → ready_for_preview."""
    flow, _interpreter, _replier = _make_flow()
    session = Session(session_id="bpo-session")
    msg1 = (
        "We run a BPO contact center in Manila called Nexora Connect. "
        "We need customer care, billing, and technical support queues with "
        "QA dashboards for 280 employees."
    )
    history = [ConversationMessage(role="user", content=msg1)]

    turn1 = await flow.process_turn(
        ConversationTurnRequest(
            session_id="bpo-session",
            user_message=msg1,
            history=history,
            session=session,
        )
    )
    assert turn1["status"] == "pending_confirmation"

    history.append(
        ConversationMessage(
            role="assistant", content=str(turn1.get("message") or "")
        )
    )
    msg2 = "yes please"
    history.append(ConversationMessage(role="user", content=msg2))

    turn2 = await flow.process_turn(
        ConversationTurnRequest(
            session_id="bpo-session",
            user_message=msg2,
            history=history,
            session=session,
        )
    )
    assert turn2["status"] == "ready_for_preview"
    assert turn2["bundle_key"] == "ticketing"
