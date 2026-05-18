"""Tests for natural-language confirmation intent detection.

Covers:
- _detect_confirmation_intent() positive and negative cases
- process_turn() short-circuits to ready_for_preview when confirmation intent
  is detected, bundle is proposed, and session is not yet confirmed
- Guard conditions: no short-circuit when already confirmed or no bundle proposed
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from catalog.bundle_catalog import BundleCatalog
from domain.models.bundle import BundleSuggestion
from domain.models.classification_result import ClassificationResult
from domain.models.conversation import ConversationMessage
from domain.models.extraction_result import ExtractionResult
from domain.models.session import Session
from orchestrators.conversation_flow import (
    ConversationFlow,
    ConversationTurnRequest,
    _detect_confirmation_intent,
)


# ---------------------------------------------------------------------------
# Unit tests for _detect_confirmation_intent
# ---------------------------------------------------------------------------


class TestDetectConfirmationIntent:
    @pytest.mark.parametrize(
        "message",
        [
            "go ahead",
            "Go ahead please",
            "proceed",
            "Yes, proceed with that",
            "looks good",
            "Looks good to me!",
            "yes please",
            "sounds good",
            "confirm",
            "do it",
            "that works",
            "let's do it",
            "yes",
            "no, go ahead",  # leading "no" separated by comma — not a negation
        ],
    )
    def test_positive_phrases(self, message: str) -> None:
        assert _detect_confirmation_intent(message) is True

    @pytest.mark.parametrize(
        "message",
        [
            "don't go ahead",
            "do not proceed",
            "not looks good",
            "never do it",
            "no go ahead",  # "no" immediately before phrase with no comma boundary
            "please don't confirm",
            "I don't think that works",
        ],
    )
    def test_negated_phrases(self, message: str) -> None:
        assert _detect_confirmation_intent(message) is False

    @pytest.mark.parametrize(
        "message",
        [
            "what do you think?",
            "I need more information",
            "can you change the bundle?",
            "",
        ],
    )
    def test_unrelated_messages(self, message: str) -> None:
        assert _detect_confirmation_intent(message) is False


# ---------------------------------------------------------------------------
# Helpers shared by process_turn tests
# ---------------------------------------------------------------------------


def _make_flow(shared_catalog: BundleCatalog) -> tuple[ConversationFlow, MagicMock, MagicMock]:
    required_slots = {b.bundle_key: b.required_slots for b in shared_catalog.list_all()}
    interpreter = MagicMock()
    interpreter.summarize_history = AsyncMock(return_value="")
    interpreter.interpret = AsyncMock(
        return_value=(
            ExtractionResult(session_id="s1"),
            ClassificationResult(
                session_id="s1",
                selected_bundle=BundleSuggestion(
                    bundle_key="hr_core",
                    display_name="HR Core",
                    confidence=0.9,
                    reasoning="High confidence",
                    matched_signals=[],
                ),
                ranked_candidates=[],
                confidence_status="proceed",
                top_confidence=0.9,
                score_gap=0.4,
                missing_context=[],
                reasoning="High confidence HR bundle",
            ),
        )
    )
    interpreter.extract_only = AsyncMock(return_value=ExtractionResult(session_id="s1"))
    interpreter.top_bundle = MagicMock(
        return_value=BundleSuggestion(
            bundle_key="hr_core",
            display_name="HR Core",
            confidence=0.9,
            reasoning="High confidence",
            matched_signals=[],
        )
    )
    replier = MagicMock()
    replier.build_clarification = AsyncMock(return_value=(None, ""))
    replier.build_bundle_suggestion = AsyncMock(return_value="Here is the HR bundle.")
    flow = ConversationFlow(
        interpreter_service=interpreter,
        replier_service=replier,
        bundle_catalog=shared_catalog,
        required_slots_by_bundle=required_slots,
    )
    return flow, interpreter, replier


def _make_session_with_proposed_bundle(bundle_key: str = "hr_core") -> Session:
    """Return a session where a bundle has been proposed but not yet confirmed."""
    return Session(
        session_id="s1",
        selected_bundle_key=bundle_key,
        confirmed=False,
    )


# ---------------------------------------------------------------------------
# process_turn integration tests
# ---------------------------------------------------------------------------


class TestProcessTurnConfirmationShortCircuit:
    @pytest.mark.asyncio
    async def test_go_ahead_returns_ready_for_preview(self, shared_catalog: BundleCatalog) -> None:
        flow, interpreter, _replier = _make_flow(shared_catalog)
        session = _make_session_with_proposed_bundle()

        result = await flow.process_turn(
            ConversationTurnRequest(
                session_id="s1",
                user_message="go ahead",
                history=[ConversationMessage(role="user", content="go ahead")],
                session=session,
            )
        )

        assert result["status"] == "ready_for_preview"
        assert result["preview_type"] == "confirmed"

    @pytest.mark.asyncio
    async def test_confirmation_sets_session_confirmed(self, shared_catalog: BundleCatalog) -> None:
        flow, _interpreter, _replier = _make_flow(shared_catalog)
        session = _make_session_with_proposed_bundle()

        await flow.process_turn(
            ConversationTurnRequest(
                session_id="s1",
                user_message="proceed",
                history=[ConversationMessage(role="user", content="proceed")],
                session=session,
            )
        )

        assert session.confirmed is True

    @pytest.mark.asyncio
    async def test_no_short_circuit_when_already_confirmed(
        self, shared_catalog: BundleCatalog
    ) -> None:
        flow, _interpreter, replier = _make_flow(shared_catalog)
        session = Session(
            session_id="s1",
            selected_bundle_key="hr_core",
            confirmed=True,
        )

        result = await flow.process_turn(
            ConversationTurnRequest(
                session_id="s1",
                user_message="go ahead",
                history=[ConversationMessage(role="user", content="go ahead")],
                session=session,
            )
        )

        # Falls through to normal flow — already confirmed means ready_for_preview
        # via the final branch, not the short-circuit; either way confirmed stays True
        assert session.confirmed is True
        assert result["status"] == "ready_for_preview"

    @pytest.mark.asyncio
    async def test_no_short_circuit_when_no_bundle_proposed(
        self, shared_catalog: BundleCatalog
    ) -> None:
        flow, interpreter, replier = _make_flow(shared_catalog)
        # Make interpreter return clarify so we know we went through normal flow
        interpreter.interpret = AsyncMock(
            return_value=(
                ExtractionResult(session_id="s1"),
                ClassificationResult(
                    session_id="s1",
                    selected_bundle=None,
                    ranked_candidates=[],
                    confidence_status="clarify",
                    top_confidence=0.0,
                    score_gap=0.0,
                    missing_context=["primary_use_case"],
                    reasoning="No bundle yet",
                ),
            )
        )
        interpreter.top_bundle = MagicMock(return_value=None)
        replier.build_clarification = AsyncMock(
            return_value=("primary_use_case", "What do you need?")
        )
        session = Session(session_id="s1", selected_bundle_key=None, confirmed=False)

        result = await flow.process_turn(
            ConversationTurnRequest(
                session_id="s1",
                user_message="go ahead",
                history=[ConversationMessage(role="user", content="go ahead")],
                session=session,
            )
        )

        # Short-circuit must NOT fire; normal clarification flow should run
        assert result["status"] == "awaiting_input"
        assert session.confirmed is False

    @pytest.mark.asyncio
    async def test_negated_phrase_does_not_confirm(self, shared_catalog: BundleCatalog) -> None:
        flow, interpreter, replier = _make_flow(shared_catalog)
        interpreter.interpret = AsyncMock(
            return_value=(
                ExtractionResult(session_id="s1"),
                ClassificationResult(
                    session_id="s1",
                    selected_bundle=None,
                    ranked_candidates=[],
                    confidence_status="clarify",
                    top_confidence=0.0,
                    score_gap=0.0,
                    missing_context=["primary_use_case"],
                    reasoning="No bundle yet",
                ),
            )
        )
        interpreter.top_bundle = MagicMock(return_value=None)
        replier.build_clarification = AsyncMock(
            return_value=("primary_use_case", "What do you need?")
        )
        session = _make_session_with_proposed_bundle()

        result = await flow.process_turn(
            ConversationTurnRequest(
                session_id="s1",
                user_message="don't go ahead",
                history=[ConversationMessage(role="user", content="don't go ahead")],
                session=session,
            )
        )

        assert session.confirmed is False
        assert result["status"] != "ready_for_preview"
