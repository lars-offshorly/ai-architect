"""Unit tests for ConversationFlow pre-selection and pre-filled intent paths."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from catalog.bundle_catalog import BundleCatalog
from domain.enums.missing_field_type import MissingFieldType
from domain.models.bundle import BundleSuggestion
from domain.models.classification_result import ClassificationResult
from domain.models.conversation import ConversationMessage
from domain.models.extraction_result import ExtractionResult
from orchestrators.conversation_flow import (
    ConversationFlow,
    InterpreterPort,
    ReplierPort,
)

# pylint: disable=duplicate-code

REGISTRY_PATH = (
    Path(__file__).resolve().parents[3] / "src/templates/bundle_registry.yaml"
)

_PRESELECTED_KEY = "hr_management"


def _make_flow(
    interpreter: InterpreterPort,
    replier: ReplierPort,
) -> ConversationFlow:
    catalog = BundleCatalog(REGISTRY_PATH)
    required_slots = {b.bundle_key: b.required_slots for b in catalog.list_all()}
    return ConversationFlow(
        interpreter_service=interpreter,
        replier_service=replier,
        bundle_catalog=catalog,
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


def _make_replier_mock() -> MagicMock:
    replier = MagicMock()
    replier.build_clarification = AsyncMock(
        return_value=(MissingFieldType.PRIMARY_USE_CASE, "What is your use case?")
    )
    replier.build_bundle_suggestion = AsyncMock(return_value="Here is your bundle")
    return replier


class TestPreselectedBundleBypassesClassification:
    @pytest.mark.asyncio
    async def test_top_bundle_not_called_when_preselected(self) -> None:
        extraction = ExtractionResult(session_id="s1")
        interpreter = _make_interpreter_mock(extraction)
        replier = _make_replier_mock()
        flow = _make_flow(interpreter, replier)

        await flow.process_turn(
            session_id="s1",
            user_message="I need HR",
            accumulated_extraction=None,
            history=[ConversationMessage(role="user", content="I need HR")],
            confirmed=False,
            preselected_bundle_key=_PRESELECTED_KEY,
        )

        interpreter.top_bundle.assert_not_called()

    @pytest.mark.asyncio
    async def test_extract_only_called_on_preselected_path(self) -> None:
        extraction = ExtractionResult(session_id="s1")
        interpreter = _make_interpreter_mock(extraction)
        replier = _make_replier_mock()
        flow = _make_flow(interpreter, replier)

        await flow.process_turn(
            session_id="s1",
            user_message="I need HR",
            accumulated_extraction=None,
            history=[ConversationMessage(role="user", content="I need HR")],
            confirmed=False,
            preselected_bundle_key=_PRESELECTED_KEY,
        )

        interpreter.extract_only.assert_awaited_once()
        interpreter.interpret.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_mock_suggestion_has_full_confidence(self) -> None:
        extraction = ExtractionResult(session_id="s1")
        interpreter = _make_interpreter_mock(extraction)
        replier = _make_replier_mock()
        replier.build_clarification = AsyncMock(return_value=(None, None))
        replier.build_bundle_suggestion = AsyncMock(return_value="Suggestion")
        flow = _make_flow(interpreter, replier)

        result = await flow.process_turn(
            session_id="s1",
            user_message="I need HR",
            accumulated_extraction=None,
            history=[ConversationMessage(role="user", content="I need HR")],
            confirmed=False,
            preselected_bundle_key=_PRESELECTED_KEY,
        )

        classification = result["classification"]
        assert classification.selected_bundle is not None
        assert classification.selected_bundle.bundle_key == _PRESELECTED_KEY
        assert classification.selected_bundle.confidence == 1.0
        assert classification.selected_bundle.reasoning == "Pre-selected by user"

    @pytest.mark.asyncio
    async def test_bundle_key_in_result_matches_preselected(self) -> None:
        extraction = ExtractionResult(session_id="s1")
        interpreter = _make_interpreter_mock(extraction)
        replier = _make_replier_mock()
        replier.build_clarification = AsyncMock(return_value=(None, None))
        replier.build_bundle_suggestion = AsyncMock(return_value="Suggestion")
        flow = _make_flow(interpreter, replier)

        result = await flow.process_turn(
            session_id="s1",
            user_message="I need HR",
            accumulated_extraction=None,
            history=[ConversationMessage(role="user", content="I need HR")],
            confirmed=False,
            preselected_bundle_key=_PRESELECTED_KEY,
        )

        assert result.get("bundle_key") == _PRESELECTED_KEY


class TestPreselectedBundleDoesNotBreakNormalFlow:
    @pytest.mark.asyncio
    async def test_normal_flow_without_preselection_unchanged(self) -> None:
        extraction = ExtractionResult(session_id="s2")
        interpreter = _make_interpreter_mock(extraction)
        replier = _make_replier_mock()
        flow = _make_flow(interpreter, replier)

        await flow.process_turn(
            session_id="s2",
            user_message="I need something",
            accumulated_extraction=None,
            history=[ConversationMessage(role="user", content="I need something")],
            confirmed=False,
        )

        interpreter.top_bundle.assert_called_once()
        interpreter.interpret.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_missing_field_detection_runs_with_preselected_bundle(self) -> None:
        extraction = ExtractionResult(session_id="s1")
        interpreter = _make_interpreter_mock(extraction)
        replier = _make_replier_mock()
        flow = _make_flow(interpreter, replier)

        result = await flow.process_turn(
            session_id="s1",
            user_message="I need HR",
            accumulated_extraction=None,
            history=[ConversationMessage(role="user", content="I need HR")],
            confirmed=False,
            preselected_bundle_key=_PRESELECTED_KEY,
        )

        assert "extracted" in result
        extracted: ExtractionResult = result["extracted"]  # type: ignore[assignment]
        assert extracted.missing_fields is not None


_PRESELECTED_INTENT = "manage employees"


class TestPrefilledIntentInjection:
    @pytest.mark.asyncio
    async def test_interpret_called_with_preselected_intent(self) -> None:
        extraction = ExtractionResult(session_id="s3")
        interpreter = _make_interpreter_mock(extraction)
        replier = _make_replier_mock()
        flow = _make_flow(interpreter, replier)

        await flow.process_turn(
            session_id="s3",
            user_message="I need an HR system",
            accumulated_extraction=None,
            history=[ConversationMessage(role="user", content="I need an HR system")],
            confirmed=False,
            preselected_intent=_PRESELECTED_INTENT,
        )

        request = interpreter.interpret.call_args.args[0]
        assert request.preselected_intent == _PRESELECTED_INTENT

    @pytest.mark.asyncio
    async def test_extract_only_called_with_intent_and_preselected_bundle(self) -> None:
        extraction = ExtractionResult(session_id="s4")
        interpreter = _make_interpreter_mock(extraction)
        replier = _make_replier_mock()
        replier.build_clarification = AsyncMock(return_value=(None, None))
        replier.build_bundle_suggestion = AsyncMock(return_value="Suggestion")
        flow = _make_flow(interpreter, replier)

        result = await flow.process_turn(
            session_id="s4",
            user_message="I need an HR system",
            accumulated_extraction=None,
            history=[ConversationMessage(role="user", content="I need an HR system")],
            confirmed=False,
            preselected_bundle_key=_PRESELECTED_KEY,
            preselected_intent=_PRESELECTED_INTENT,
        )

        request = interpreter.extract_only.call_args.args[0]
        assert request.preselected_intent == _PRESELECTED_INTENT
        interpreter.interpret.assert_not_awaited()
        classification = result["classification"]
        assert classification.selected_bundle is not None
        assert classification.selected_bundle.bundle_key == _PRESELECTED_KEY

    @pytest.mark.asyncio
    async def test_no_intent_forwarded_when_not_provided(self) -> None:
        extraction = ExtractionResult(session_id="s5")
        interpreter = _make_interpreter_mock(extraction)
        replier = _make_replier_mock()
        flow = _make_flow(interpreter, replier)

        await flow.process_turn(
            session_id="s5",
            user_message="I need something",
            accumulated_extraction=None,
            history=[ConversationMessage(role="user", content="I need something")],
            confirmed=False,
        )

        request = interpreter.interpret.call_args.args[0]
        assert request.preselected_intent is None


class TestForcePreviewing:
    @pytest.mark.asyncio
    async def test_force_preview_returns_ready_for_preview_with_warning(self) -> None:
        extraction = ExtractionResult(session_id="s6")
        interpreter = _make_interpreter_mock(extraction)
        interpreter.top_bundle = MagicMock(
            return_value=MagicMock(bundle_key="hr_management")
        )
        replier = _make_replier_mock()
        flow = _make_flow(interpreter, replier)

        result = await flow.process_turn(
            session_id="s6",
            user_message="I need an HR tool",
            accumulated_extraction=None,
            history=[ConversationMessage(role="user", content="I need an HR tool")],
            confirmed=False,
            force_preview=True,
        )

        assert result["status"] == "ready_for_preview"
        assert result.get("warning") is not None
        assert "incomplete" in str(result.get("warning")).lower()
        assert result.get("preview_type") == "early"

    @pytest.mark.asyncio
    async def test_force_preview_does_not_call_replier(self) -> None:
        extraction = ExtractionResult(session_id="s7")
        interpreter = _make_interpreter_mock(extraction)
        interpreter.top_bundle = MagicMock(
            return_value=MagicMock(bundle_key="ticketing")
        )
        replier = _make_replier_mock()
        flow = _make_flow(interpreter, replier)

        await flow.process_turn(
            session_id="s7",
            user_message="build it now",
            accumulated_extraction=None,
            history=[ConversationMessage(role="user", content="build it now")],
            confirmed=False,
            force_preview=True,
        )

        replier.build_clarification.assert_not_awaited()
        replier.build_bundle_suggestion.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_preview_keyword_in_message_triggers_early_preview(self) -> None:
        extraction = ExtractionResult(session_id="s8")
        interpreter = _make_interpreter_mock(extraction)
        interpreter.top_bundle = MagicMock(
            return_value=MagicMock(bundle_key="ticketing")
        )
        replier = _make_replier_mock()
        flow = _make_flow(interpreter, replier)

        result = await flow.process_turn(
            session_id="s8",
            user_message="preview now",
            accumulated_extraction=None,
            history=[ConversationMessage(role="user", content="preview now")],
            confirmed=False,
            force_preview=False,
        )

        assert result["status"] == "ready_for_preview"
        assert result.get("preview_type") == "early"
        assert result.get("warning") is not None

    @pytest.mark.asyncio
    async def test_force_preview_with_preselected_bundle_returns_preselected_key(
        self,
    ) -> None:
        extraction = ExtractionResult(session_id="s9")
        interpreter = _make_interpreter_mock(extraction)
        replier = _make_replier_mock()
        flow = _make_flow(interpreter, replier)

        result = await flow.process_turn(
            session_id="s9",
            user_message="show preview",
            accumulated_extraction=None,
            history=[ConversationMessage(role="user", content="show preview")],
            confirmed=False,
            preselected_bundle_key=_PRESELECTED_KEY,
            force_preview=True,
        )

        assert result["status"] == "ready_for_preview"
        assert result.get("bundle_key") == _PRESELECTED_KEY
        assert result.get("preview_type") == "early"

    @pytest.mark.asyncio
    async def test_force_preview_falls_back_to_generic_when_no_bundle(
        self,
    ) -> None:
        extraction = ExtractionResult(session_id="s11")
        interpreter = _make_interpreter_mock(extraction)
        replier = _make_replier_mock()
        flow = _make_flow(interpreter, replier)

        result = await flow.process_turn(
            session_id="s11",
            user_message="just show me anything",
            accumulated_extraction=None,
            history=[ConversationMessage(role="user", content="just show me anything")],
            confirmed=False,
            force_preview=True,
        )

        assert result["status"] == "ready_for_preview"
        assert result.get("bundle_key") == "generic"
        assert result.get("preview_type") == "early"
        assert result.get("warning") is not None

    @pytest.mark.asyncio
    async def test_confirmed_path_returns_preview_type_confirmed(
        self,
    ) -> None:
        extraction = ExtractionResult(session_id="s12")
        interpreter = _make_interpreter_mock(extraction)
        interpreter.top_bundle = MagicMock(
            return_value=MagicMock(bundle_key="hr_management")
        )
        replier = _make_replier_mock()
        replier.build_clarification = AsyncMock(return_value=(None, None))
        flow = _make_flow(interpreter, replier)

        result = await flow.process_turn(
            session_id="s12",
            user_message="yes confirm",
            accumulated_extraction=None,
            history=[ConversationMessage(role="user", content="yes confirm")],
            confirmed=True,
        )

        assert result["status"] == "ready_for_preview"
        assert result.get("preview_type") == "confirmed"
        assert result.get("warning") is None

    @pytest.mark.asyncio
    async def test_no_force_preview_and_no_keyword_continues_normal_flow(
        self,
    ) -> None:
        extraction = ExtractionResult(session_id="s10")
        interpreter = _make_interpreter_mock(extraction)
        replier = _make_replier_mock()
        flow = _make_flow(interpreter, replier)

        result = await flow.process_turn(
            session_id="s10",
            user_message="I need something",
            accumulated_extraction=None,
            history=[ConversationMessage(role="user", content="I need something")],
            confirmed=False,
            force_preview=False,
        )

        assert result.get("preview_type") is None
        assert result.get("warning") is None
