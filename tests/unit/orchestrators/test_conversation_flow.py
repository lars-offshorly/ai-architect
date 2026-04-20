from __future__ import annotations

# pylint: disable=duplicate-code
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from catalog.bundle_catalog import BundleCatalog
from domain.enums.missing_field_type import MissingFieldType
from domain.models.bundle import BundleSuggestion
from domain.models.classification_result import ClassificationResult
from domain.models.conversation import ConversationMessage
from domain.models.extraction_result import ExtractionResult
from orchestrators.conversation_flow import ConversationFlow, ConversationTurnRequest

REGISTRY_PATH = (
    Path(__file__).resolve().parents[3] / "src/templates/bundle_registry.yaml"
)


@pytest.mark.asyncio
async def test_process_turn_summarizes_prior_history_and_forwards_summary(shared_catalog: BundleCatalog) -> None:
    required_slots = {
        bundle.bundle_key: bundle.required_slots for bundle in shared_catalog.list_all()
    }

    interpreter = MagicMock()
    interpreter.summarize_history = AsyncMock(return_value="prior summary")
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
                reasoning="No bundles classified",
            ),
        )
    )
    interpreter.top_bundle = MagicMock(return_value=None)

    replier = MagicMock()
    replier.build_clarification = AsyncMock(
        return_value=(MissingFieldType.PRIMARY_USE_CASE, "What is your use case?")
    )

    flow = ConversationFlow(
        interpreter_service=interpreter,
        replier_service=replier,
        bundle_catalog=shared_catalog,
        required_slots_by_bundle=required_slots,
    )
    history = [
        ConversationMessage(role="user", content="hello"),
        ConversationMessage(role="assistant", content="hi"),
        ConversationMessage(role="user", content="latest"),
    ]

    await flow.process_turn(
        ConversationTurnRequest(
            session_id="s1",
            user_message="latest",
            history=history,
            confirmed=False,
            accumulated_extraction=None,
        )
    )

    interpreter.summarize_history.assert_awaited_once_with("s1", history[:-1], None)
    assert interpreter.interpret.call_args.args[0].summary == "prior summary"
