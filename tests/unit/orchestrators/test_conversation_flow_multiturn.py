"""Multi-turn signal accumulation and session persistence tests for ConversationFlow.

These tests verify that accumulated_extraction is correctly passed between turns,
that the summarizer receives prior extraction context, and that missing fields
are re-evaluated per turn using the current merged extraction state.
"""

from __future__ import annotations

# pylint: disable=duplicate-code
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from catalog.bundle_catalog import BundleCatalog
from domain.enums.missing_field_type import MissingFieldType
from domain.models.bundle import BundleSuggestion
from domain.models.classification_result import ClassificationResult
from domain.models.conversation import ConversationMessage
from domain.models.extraction_result import (
    ClassificationSignals,
    ExtractionResult,
    PersonalizationSignals,
)
from orchestrators.conversation_flow import (
    ConversationFlow,
    ConversationTurnRequest,
    InterpreterPort,
    ReplierPort,
)

REGISTRY_PATH = (
    Path(__file__).resolve().parents[3] / "src/templates/bundle_registry.yaml"
)


def _make_flow(
    interpreter: InterpreterPort,
    replier: ReplierPort,
    shared_catalog: BundleCatalog,
) -> ConversationFlow:
    required_slots = {b.bundle_key: b.required_slots for b in shared_catalog.list_all()}
    return ConversationFlow(
        interpreter_service=interpreter,
        replier_service=replier,
        bundle_catalog=shared_catalog,
        required_slots_by_bundle=required_slots,
    )


def _make_interpreter_mock(extraction: ExtractionResult) -> MagicMock:
    interpreter = MagicMock()
    interpreter.summarize_history = AsyncMock(return_value="")
    interpreter.interpret = AsyncMock(
        return_value=(
            extraction,
            ClassificationResult(
                session_id="s1",
                selected_bundle=None,
                ranked_candidates=[],
                confidence_status="clarify",
                top_confidence=0.0,
                score_gap=0.0,
                missing_context=["primary_use_case"],
                reasoning="No bundles classified",
            ),
        )
    )
    interpreter.extract_only = AsyncMock(return_value=extraction)
    interpreter.top_bundle = MagicMock(return_value=None)
    return interpreter


def _make_replier_clarify_mock(field: MissingFieldType, question: str) -> MagicMock:
    replier = MagicMock()
    replier.build_clarification = AsyncMock(return_value=(field, question))
    replier.build_bundle_suggestion = AsyncMock(return_value="Here is your bundle")
    return replier


def _make_replier_no_missing_mock() -> MagicMock:
    replier = MagicMock()
    replier.build_clarification = AsyncMock(return_value=(None, ""))
    replier.build_bundle_suggestion = AsyncMock(return_value="Bundle looks good!")
    return replier


class TestMultiTurnAccumulatedExtractionPassing:
    """Verify `accumulated_extraction` is carried across turns."""

    @pytest.mark.asyncio
    async def test_turn1_result_contains_extracted(self, shared_catalog: BundleCatalog) -> None:
        extraction = ExtractionResult(
            session_id="s1",
            classification_signals=ClassificationSignals(keywords=["hr"]),
        )
        interpreter = _make_interpreter_mock(extraction)
        replier = _make_replier_clarify_mock(
            MissingFieldType.PRIMARY_USE_CASE, "What do you want to manage?"
        )
        flow = _make_flow(interpreter, replier, shared_catalog)

        result = await flow.process_turn(
            ConversationTurnRequest(
                session_id="s1",
                user_message="I need an HR system",
                history=[
                    ConversationMessage(role="user", content="I need an HR system")
                ],
                confirmed=False,
                accumulated_extraction=None,
            )
        )

        assert result["extracted"] is not None
        extracted = result["extracted"]
        assert isinstance(extracted, ExtractionResult)

    @pytest.mark.asyncio
    async def test_turn2_receives_accumulated_extraction_from_turn1(self, shared_catalog: BundleCatalog) -> None:
        turn1_extraction = ExtractionResult(
            session_id="s1",
            classification_signals=ClassificationSignals(keywords=["hr"]),
        )
        interpreter = _make_interpreter_mock(turn1_extraction)
        replier = _make_replier_clarify_mock(
            MissingFieldType.PRIMARY_USE_CASE, "What do you want to manage?"
        )
        flow = _make_flow(interpreter, replier, shared_catalog)

        turn1_result = await flow.process_turn(
            ConversationTurnRequest(
                session_id="s1",
                user_message="I need an HR system",
                history=[
                    ConversationMessage(role="user", content="I need an HR system")
                ],
                confirmed=False,
                accumulated_extraction=None,
            )
        )

        prior_extraction = turn1_result["extracted"]
        turn2_extraction = ExtractionResult(
            session_id="s1",
            classification_signals=ClassificationSignals(
                keywords=["leave", "employee"]
            ),
        )
        interpreter.interpret = AsyncMock(
            return_value=(
                turn2_extraction,
                ClassificationResult(
                    session_id="s1",
                    selected_bundle=None,
                    ranked_candidates=[],
                    confidence_status="clarify",
                    top_confidence=0.0,
                    score_gap=0.0,
                    missing_context=["primary_use_case"],
                    reasoning="No bundles classified",
                ),
            )
        )

        await flow.process_turn(
            ConversationTurnRequest(
                session_id="s1",
                user_message="We also need leave tracking",
                history=[
                    ConversationMessage(role="user", content="I need an HR system"),
                    ConversationMessage(
                        role="assistant", content="What do you want to manage?"
                    ),
                    ConversationMessage(
                        role="user", content="We also need leave tracking"
                    ),
                ],
                confirmed=False,
                accumulated_extraction=prior_extraction,  # type: ignore[arg-type]
            )
        )

        turn2_call_args = interpreter.interpret.call_args
        turn2_request = turn2_call_args[0][0]
        assert turn2_request.accumulated_extraction is prior_extraction

    @pytest.mark.asyncio
    async def test_turn1_passes_none_accumulated_extraction_to_interpreter(
        self, shared_catalog: BundleCatalog
    ) -> None:
        extraction = ExtractionResult(session_id="s1")
        interpreter = _make_interpreter_mock(extraction)
        replier = _make_replier_clarify_mock(
            MissingFieldType.PRIMARY_USE_CASE, "What do you want to manage?"
        )
        flow = _make_flow(interpreter, replier, shared_catalog)

        await flow.process_turn(
            ConversationTurnRequest(
                session_id="s1",
                user_message="Hello",
                history=[ConversationMessage(role="user", content="Hello")],
                confirmed=False,
                accumulated_extraction=None,
            )
        )

        turn1_request = interpreter.interpret.call_args[0][0]
        assert turn1_request.accumulated_extraction is None


class TestMultiTurnSummarizerReceivesAccumulatedExtraction:
    """Verify summarizer receives accumulated_extraction on subsequent turns."""

    @pytest.mark.asyncio
    async def test_first_turn_summarizer_receives_no_accumulated_extraction(
        self, shared_catalog: BundleCatalog
    ) -> None:
        extraction = ExtractionResult(session_id="s1")
        interpreter = _make_interpreter_mock(extraction)
        replier = _make_replier_clarify_mock(
            MissingFieldType.PRIMARY_USE_CASE, "What do you want to manage?"
        )
        flow = _make_flow(interpreter, replier, shared_catalog)

        await flow.process_turn(
            ConversationTurnRequest(
                session_id="s1",
                user_message="Hello",
                history=[ConversationMessage(role="user", content="Hello")],
                confirmed=False,
                accumulated_extraction=None,
            )
        )

        interpreter.summarize_history.assert_awaited_once_with("s1", [], None)

    @pytest.mark.asyncio
    async def test_second_turn_summarizer_receives_prior_accumulated_extraction(
        self, shared_catalog: BundleCatalog
    ) -> None:
        prior_extraction = ExtractionResult(
            session_id="s1",
            classification_signals=ClassificationSignals(keywords=["hr"]),
        )
        extraction = ExtractionResult(session_id="s1")
        interpreter = _make_interpreter_mock(extraction)
        replier = _make_replier_clarify_mock(
            MissingFieldType.ENTITY_TYPE, "What entity do you track?"
        )
        flow = _make_flow(interpreter, replier, shared_catalog)

        history = [
            ConversationMessage(role="user", content="Turn 1"),
            ConversationMessage(role="assistant", content="Question?"),
            ConversationMessage(role="user", content="Turn 2"),
        ]

        await flow.process_turn(
            ConversationTurnRequest(
                session_id="s1",
                user_message="Turn 2",
                history=history,
                confirmed=False,
                accumulated_extraction=prior_extraction,
            )
        )

        interpreter.summarize_history.assert_awaited_once_with(
            "s1", history[:-1], prior_extraction
        )


class TestMissingFieldsRecomputedPerTurn:
    """Missing fields are re-evaluated each turn on merged extraction."""

    @pytest.mark.asyncio
    async def test_missing_fields_populated_on_result_extraction(self, shared_catalog: BundleCatalog) -> None:
        extraction = ExtractionResult(
            session_id="s1",
            classification_signals=ClassificationSignals(
                keywords=["leave"], entities=[], workflow_hints=[]
            ),
        )
        interpreter = _make_interpreter_mock(extraction)
        replier = _make_replier_clarify_mock(
            MissingFieldType.PRIMARY_USE_CASE, "What do you want to manage?"
        )
        flow = _make_flow(interpreter, replier, shared_catalog)

        result = await flow.process_turn(
            ConversationTurnRequest(
                session_id="s1",
                user_message="We track leave",
                history=[ConversationMessage(role="user", content="We track leave")],
                confirmed=False,
                accumulated_extraction=None,
            )
        )

        result_extraction = result["extracted"]
        assert isinstance(result_extraction, ExtractionResult)
        assert isinstance(result_extraction.missing_fields, list)

    @pytest.mark.asyncio
    async def test_no_missing_fields_when_full_extraction_provided(self, shared_catalog: BundleCatalog) -> None:
        extraction = ExtractionResult(
            session_id="s1",
            classification_signals=ClassificationSignals(
                keywords=["leave management"],
                entities=["employee"],
                intents=["handle leave requests"],
                workflow_hints=["employee leave workflow"],
            ),
            personalization_signals=PersonalizationSignals(company_name="Acme"),
        )
        interpreter = _make_interpreter_mock(extraction)
        top_bundle = BundleSuggestion(
            bundle_key="hr_management",
            display_name="HR Management",
            confidence=0.9,
            reasoning="Strong match",
            matched_signals=["employee", "leave"],
        )
        interpreter.top_bundle = MagicMock(return_value=top_bundle)
        classification = ClassificationResult(
            session_id="s1",
            selected_bundle=top_bundle,
            ranked_candidates=[top_bundle],
            confidence_status="proceed",
            top_confidence=0.9,
            score_gap=0.0,
            missing_context=[],
            reasoning="Strong match",
        )
        interpreter.interpret = AsyncMock(return_value=(extraction, classification))
        replier = _make_replier_no_missing_mock()
        flow = _make_flow(interpreter, replier, shared_catalog)

        result = await flow.process_turn(
            ConversationTurnRequest(
                session_id="s1",
                user_message="We need leave management",
                history=[
                    ConversationMessage(role="user", content="We need leave management")
                ],
                confirmed=False,
            )
        )

        assert result["status"] == "pending_confirmation"


class TestSessionStatePersistenceSimulation:
    # Pylint flags test classes with one test method; pytest grouping is intentional.
    # pylint: disable=too-few-public-methods
    """Simulate persistence where turn N feeds turn N+1 extraction."""

    @pytest.mark.asyncio
    async def test_three_turn_session_carries_extraction_chain(self, shared_catalog: BundleCatalog) -> None:
        turn1_extraction = ExtractionResult(
            session_id="s1",
            classification_signals=ClassificationSignals(keywords=["hr"]),
        )
        interpreter = _make_interpreter_mock(turn1_extraction)
        replier = _make_replier_clarify_mock(
            MissingFieldType.PRIMARY_USE_CASE, "What do you want to manage?"
        )
        flow = _make_flow(interpreter, replier, shared_catalog)

        t1_result = await flow.process_turn(
            ConversationTurnRequest(
                session_id="s1",
                user_message="I want HR",
                history=[ConversationMessage(role="user", content="I want HR")],
                confirmed=False,
                accumulated_extraction=None,
            )
        )
        session_extraction_after_t1 = t1_result["extracted"]

        turn2_extraction = ExtractionResult(
            session_id="s1",
            classification_signals=ClassificationSignals(
                keywords=["leave", "employee"]
            ),
        )
        interpreter.interpret = AsyncMock(
            return_value=(
                turn2_extraction,
                ClassificationResult(
                    session_id="s1",
                    selected_bundle=None,
                    ranked_candidates=[],
                    confidence_status="clarify",
                    top_confidence=0.0,
                    score_gap=0.0,
                    missing_context=["primary_use_case"],
                    reasoning="No bundles classified",
                ),
            )
        )

        t2_result = await flow.process_turn(
            ConversationTurnRequest(
                session_id="s1",
                user_message="Leave tracking",
                history=[
                    ConversationMessage(role="user", content="I want HR"),
                    ConversationMessage(role="assistant", content="What do you want?"),
                    ConversationMessage(role="user", content="Leave tracking"),
                ],
                confirmed=False,
                accumulated_extraction=cast(
                    ExtractionResult, session_extraction_after_t1
                ),
            )
        )
        session_extraction_after_t2 = t2_result["extracted"]

        t2_interpreter_request = interpreter.interpret.call_args[0][0]
        assert (
            t2_interpreter_request.accumulated_extraction is session_extraction_after_t1
        )

        turn3_extraction = ExtractionResult(
            session_id="s1",
            classification_signals=ClassificationSignals(keywords=["calendar"]),
        )
        interpreter.interpret = AsyncMock(
            return_value=(
                turn3_extraction,
                ClassificationResult(
                    session_id="s1",
                    selected_bundle=None,
                    ranked_candidates=[],
                    confidence_status="clarify",
                    top_confidence=0.0,
                    score_gap=0.0,
                    missing_context=["primary_use_case"],
                    reasoning="No bundles classified",
                ),
            )
        )

        await flow.process_turn(
            ConversationTurnRequest(
                session_id="s1",
                user_message="Manager approvals too",
                history=[
                    ConversationMessage(role="user", content="I want HR"),
                    ConversationMessage(role="assistant", content="What do you want?"),
                    ConversationMessage(role="user", content="Leave tracking"),
                    ConversationMessage(
                        role="assistant", content="Got it, anything else?"
                    ),
                    ConversationMessage(role="user", content="Manager approvals too"),
                ],
                confirmed=False,
                accumulated_extraction=cast(
                    ExtractionResult, session_extraction_after_t2
                ),
            )
        )

        t3_interpreter_request = interpreter.interpret.call_args[0][0]
        assert (
            t3_interpreter_request.accumulated_extraction is session_extraction_after_t2
        )
