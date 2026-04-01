from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from agents.interpreter.summarizer import Summarizer, _format_extracted_context
from domain.models.conversation import ConversationMessage
from domain.models.extraction_result import (
    ClassificationSignals,
    ExtractionResult,
    PersonalizationSignals,
)


class TestFormatExtractedContext:
    def test_returns_empty_string_for_empty_extraction(self) -> None:
        extracted = ExtractionResult(session_id="s1")
        result = _format_extracted_context(extracted)
        assert result == ""

    def test_includes_keywords_when_present(self) -> None:
        extracted = ExtractionResult(
            session_id="s1",
            classification_signals=ClassificationSignals(keywords=["hr", "leave"]),
        )
        result = _format_extracted_context(extracted)
        assert "hr" in result
        assert "leave" in result
        assert "Known keywords" in result

    def test_includes_entities_when_present(self) -> None:
        extracted = ExtractionResult(
            session_id="s1",
            classification_signals=ClassificationSignals(
                entities=["employee", "manager"]
            ),
        )
        result = _format_extracted_context(extracted)
        assert "employee" in result
        assert "Known entities" in result

    def test_includes_intents_when_present(self) -> None:
        extracted = ExtractionResult(
            session_id="s1",
            classification_signals=ClassificationSignals(intents=["approve leave"]),
        )
        result = _format_extracted_context(extracted)
        assert "approve leave" in result
        assert "Known intents" in result

    def test_includes_workflow_hints_when_present(self) -> None:
        extracted = ExtractionResult(
            session_id="s1",
            classification_signals=ClassificationSignals(
                workflow_hints=["leave approval workflow"]
            ),
        )
        result = _format_extracted_context(extracted)
        assert "leave approval workflow" in result
        assert "Workflow hints" in result

    def test_includes_company_name_when_present(self) -> None:
        extracted = ExtractionResult(
            session_id="s1",
            personalization_signals=PersonalizationSignals(company_name="Acme Corp"),
        )
        result = _format_extracted_context(extracted)
        assert "Acme Corp" in result
        assert "Company" in result

    def test_omits_absent_fields(self) -> None:
        extracted = ExtractionResult(
            session_id="s1",
            classification_signals=ClassificationSignals(keywords=["hr"]),
        )
        result = _format_extracted_context(extracted)
        assert "Known entities" not in result
        assert "Known intents" not in result
        assert "Company" not in result


class TestSummarizerWithExtractedContext:
    def _make_summarizer(
        self, summary_text: str = "A summary."
    ) -> tuple[Summarizer, MagicMock]:
        model = MagicMock()
        model.ainvoke = AsyncMock(return_value=MagicMock(content=summary_text))
        return Summarizer(model), model

    @pytest.mark.asyncio
    async def test_summarize_without_extracted_uses_messages_only(self) -> None:
        summarizer, model = self._make_summarizer()
        messages = [ConversationMessage(role="user", content="We need HR system")]
        result = await summarizer.summarize("s1", messages)

        assert result.summary_text == "A summary."
        call_args = model.ainvoke.call_args
        human_message_content = call_args[0][0][1].content
        assert "We need HR system" in human_message_content
        assert "Already extracted" not in human_message_content

    @pytest.mark.asyncio
    async def test_summarize_with_extracted_prepends_signals_to_context(self) -> None:
        summarizer, model = self._make_summarizer()
        messages = [ConversationMessage(role="user", content="We need HR system")]
        extracted = ExtractionResult(
            session_id="s1",
            classification_signals=ClassificationSignals(
                keywords=["hr"], entities=["employee"]
            ),
        )
        await summarizer.summarize("s1", messages, extracted=extracted)

        call_args = model.ainvoke.call_args
        human_message_content = call_args[0][0][1].content
        assert "Already extracted signals" in human_message_content
        assert "hr" in human_message_content
        assert "employee" in human_message_content
        assert "We need HR system" in human_message_content

    @pytest.mark.asyncio
    async def test_summarize_with_empty_extracted_does_not_prepend(self) -> None:
        summarizer, model = self._make_summarizer()
        messages = [ConversationMessage(role="user", content="Hello")]
        extracted = ExtractionResult(session_id="s1")
        await summarizer.summarize("s1", messages, extracted=extracted)

        call_args = model.ainvoke.call_args
        human_message_content = call_args[0][0][1].content
        assert "Already extracted signals" not in human_message_content

    @pytest.mark.asyncio
    async def test_summarize_returns_empty_for_no_messages(self) -> None:
        summarizer, model = self._make_summarizer()
        result = await summarizer.summarize("s1", [])

        assert result.summary_text == ""
        assert result.message_count == 0
        model.ainvoke.assert_not_called()

    @pytest.mark.asyncio
    async def test_summarize_handles_llm_failure_gracefully(self) -> None:
        model = MagicMock()
        model.ainvoke = AsyncMock(side_effect=RuntimeError("LLM error"))
        summarizer = Summarizer(model)
        messages = [ConversationMessage(role="user", content="Hello")]

        result = await summarizer.summarize("s1", messages)

        assert result.summary_text == ""
        assert result.session_id == "s1"
