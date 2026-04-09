"""Unit tests for session router — session persistence wiring (AD-3)."""

# pylint: disable=redefined-outer-name,import-outside-toplevel,too-few-public-methods

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
from domain.models.recommendation_result import RecommendationResult
from domain.models.session import Session
from repositories.conversation_repository import ConversationRepository
from repositories.session_repository import SessionRepository

_VALID_BUNDLE_KEY = "hr_management"
_VALID_INTENT = "manage employees"


def _make_extraction(session_id: str = "s1") -> ExtractionResult:
    return ExtractionResult(
        session_id=session_id,
        classification_signals=ClassificationSignals(
            keywords=["hr"], entities=["employee"]
        ),
        personalization_signals=PersonalizationSignals(company_name="Acme"),
    )


def _make_classification(session_id: str = "s1") -> ClassificationResult:
    suggestion = BundleSuggestion(
        bundle_key="hr_management",
        display_name="HR Management",
        confidence=0.9,
        reasoning="Matched HR signals",
        matched_signals=["employee", "leave"],
    )
    return ClassificationResult(
        session_id=session_id,
        selected_bundle=suggestion,
        ranked_candidates=[suggestion],
        confidence_status="proceed",
        top_confidence=0.9,
        score_gap=0.9,
        reasoning="high confidence",
    )


@pytest.fixture()
def session_repo() -> SessionRepository:
    return SessionRepository()


@pytest.fixture()
def conv_repo() -> ConversationRepository:
    return ConversationRepository()


@pytest.fixture()
def mock_flow() -> MagicMock:
    async def _process_turn(request):  # type: ignore[no-untyped-def]
        extraction = _make_extraction(request.session_id)
        classification = _make_classification(request.session_id)
        recommendation = RecommendationResult(
            session_id=request.session_id,
            primary_bundle=classification.selected_bundle,
            recommendation_status="ready",
            inferred_modules=["employees"],
            reasoning="ready",
        )
        if request.session is not None:
            request.session.accumulated_extraction = extraction
            request.session.latest_classification = classification
            request.session.latest_recommendation = recommendation
            request.session.clarification_turn_count += 1
        return {
            "status": "awaiting_input",
            "question": "What is your use case?",
            "extracted": extraction,
            "classification": classification,
            "recommendation": recommendation,
            "slots": {},
        }

    flow = MagicMock()
    flow.process_turn = AsyncMock(side_effect=_process_turn)
    return flow


@pytest.fixture()
def mock_catalog() -> MagicMock:
    catalog = MagicMock()
    catalog.has_bundle.side_effect = lambda key: key == _VALID_BUNDLE_KEY
    catalog.get_all_typical_intents.return_value = [_VALID_INTENT, "track attendance"]
    return catalog


class TestStartSessionPersistsExtraction:
    @pytest.mark.asyncio
    async def test_start_session_saves_extracted_to_session(
        self,
        session_repo: SessionRepository,
        conv_repo: ConversationRepository,
        mock_flow: MagicMock,
        mock_catalog: MagicMock,
    ) -> None:
        """start_session must persist result['extracted'] on the session."""
        from api.routers.session import start_session
        from api.schemas.request import StartSessionRequest

        body = StartSessionRequest(user_id="u1", message="I need HR management")

        response = await start_session(
            body=body,
            session_repo=session_repo,
            conv_repo=conv_repo,
            flow=mock_flow,
            catalog=mock_catalog,
        )

        # Retrieve the saved session
        saved = session_repo.get(response.session_id)
        assert saved.accumulated_extraction is not None
        assert isinstance(saved.accumulated_extraction, ExtractionResult)
        assert (
            "employee" in saved.accumulated_extraction.classification_signals.entities
        )
        assert response.debug is not None
        assert response.classification is not None
        assert response.classification.confidence_status == "proceed"

    @pytest.mark.asyncio
    async def test_start_session_increments_clarification_turn_count(
        self,
        session_repo: SessionRepository,
        conv_repo: ConversationRepository,
        mock_flow: MagicMock,
        mock_catalog: MagicMock,
    ) -> None:
        from api.routers.session import start_session
        from api.schemas.request import StartSessionRequest

        body = StartSessionRequest(user_id="u1", message="I need HR management")

        response = await start_session(
            body=body,
            session_repo=session_repo,
            conv_repo=conv_repo,
            flow=mock_flow,
            catalog=mock_catalog,
        )

        saved = session_repo.get(response.session_id)
        assert saved.clarification_turn_count == 1


class TestStartSessionValidatesPreselectedFields:
    @pytest.mark.asyncio
    async def test_invalid_preselected_bundle_key_returns_400(
        self,
        session_repo: SessionRepository,
        conv_repo: ConversationRepository,
        mock_flow: MagicMock,
        mock_catalog: MagicMock,
    ) -> None:
        from fastapi import HTTPException

        from api.routers.session import start_session
        from api.schemas.request import StartSessionRequest

        body = StartSessionRequest(
            message="Build me an app",
            preselected_bundle_key="nonexistent_bundle",
        )

        with pytest.raises(HTTPException) as exc_info:
            await start_session(
                body=body,
                session_repo=session_repo,
                conv_repo=conv_repo,
                flow=mock_flow,
                catalog=mock_catalog,
            )

        assert exc_info.value.status_code == 400
        assert "nonexistent_bundle" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_valid_preselected_bundle_key_proceeds(
        self,
        session_repo: SessionRepository,
        conv_repo: ConversationRepository,
        mock_flow: MagicMock,
        mock_catalog: MagicMock,
    ) -> None:
        from api.routers.session import start_session
        from api.schemas.request import StartSessionRequest

        body = StartSessionRequest(
            message="Build me an HR app",
            preselected_bundle_key=_VALID_BUNDLE_KEY,
        )

        response = await start_session(
            body=body,
            session_repo=session_repo,
            conv_repo=conv_repo,
            flow=mock_flow,
            catalog=mock_catalog,
        )

        assert response.session_id is not None

    @pytest.mark.asyncio
    async def test_invalid_preselected_intent_returns_400(
        self,
        session_repo: SessionRepository,
        conv_repo: ConversationRepository,
        mock_flow: MagicMock,
        mock_catalog: MagicMock,
    ) -> None:
        from fastapi import HTTPException

        from api.routers.session import start_session
        from api.schemas.request import StartSessionRequest

        body = StartSessionRequest(
            message="Build me an app",
            preselected_intent="unknown_intent_xyz",
        )

        with pytest.raises(HTTPException) as exc_info:
            await start_session(
                body=body,
                session_repo=session_repo,
                conv_repo=conv_repo,
                flow=mock_flow,
                catalog=mock_catalog,
            )

        assert exc_info.value.status_code == 400
        assert "unknown_intent_xyz" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_valid_preselected_intent_proceeds(
        self,
        session_repo: SessionRepository,
        conv_repo: ConversationRepository,
        mock_flow: MagicMock,
        mock_catalog: MagicMock,
    ) -> None:
        from api.routers.session import start_session
        from api.schemas.request import StartSessionRequest

        body = StartSessionRequest(
            message="Build me an HR app",
            preselected_intent=_VALID_INTENT,
        )

        response = await start_session(
            body=body,
            session_repo=session_repo,
            conv_repo=conv_repo,
            flow=mock_flow,
            catalog=mock_catalog,
        )

        assert response.session_id is not None

    @pytest.mark.asyncio
    async def test_html_in_preselected_bundle_key_is_sanitized(
        self,
        session_repo: SessionRepository,
        conv_repo: ConversationRepository,
        mock_flow: MagicMock,
        mock_catalog: MagicMock,
    ) -> None:
        from fastapi import HTTPException

        from api.routers.session import start_session
        from api.schemas.request import StartSessionRequest

        body = StartSessionRequest(
            message="Build me an app",
            preselected_bundle_key="<script>alert(1)</script>hr_management",
        )

        with pytest.raises(HTTPException) as exc_info:
            await start_session(
                body=body,
                session_repo=session_repo,
                conv_repo=conv_repo,
                flow=mock_flow,
                catalog=mock_catalog,
            )

        assert exc_info.value.status_code == 400


class TestReplySessionPersistsExtraction:
    @pytest.mark.asyncio
    async def test_reply_passes_accumulated_extraction_to_flow(
        self,
        session_repo: SessionRepository,
        conv_repo: ConversationRepository,
        mock_flow: MagicMock,
    ) -> None:
        """reply_to_session forwards session.accumulated_extraction to the flow."""
        from api.routers.session import reply_to_session
        from api.schemas.request import ReplyRequest

        prior_extraction = _make_extraction(session_id="s-existing")
        session = Session(
            session_id="sess-1",
            accumulated_extraction=prior_extraction,
        )
        session_repo.save(session)
        conv_repo.append_message(
            "sess-1", ConversationMessage(role="user", content="initial")
        )

        body = ReplyRequest(message="We manage leave requests")
        await reply_to_session(
            session_id="sess-1",
            body=body,
            session_repo=session_repo,
            conv_repo=conv_repo,
            flow=mock_flow,
        )

        request_arg = mock_flow.process_turn.call_args.args[0]
        passed_extraction = request_arg.session.accumulated_extraction
        assert passed_extraction is not None
        assert isinstance(passed_extraction, ExtractionResult)
        assert passed_extraction.session_id in {"s-existing", "sess-1"}

    @pytest.mark.asyncio
    async def test_reply_saves_new_extraction_to_session(
        self,
        session_repo: SessionRepository,
        conv_repo: ConversationRepository,
        mock_flow: MagicMock,
    ) -> None:
        from api.routers.session import reply_to_session
        from api.schemas.request import ReplyRequest

        session = Session(session_id="sess-2")
        session_repo.save(session)
        conv_repo.append_message(
            "sess-2", ConversationMessage(role="user", content="initial")
        )

        body = ReplyRequest(message="Leave management")
        await reply_to_session(
            session_id="sess-2",
            body=body,
            session_repo=session_repo,
            conv_repo=conv_repo,
            flow=mock_flow,
        )

        saved = session_repo.get("sess-2")
        assert saved.accumulated_extraction is not None
        assert isinstance(saved.accumulated_extraction, ExtractionResult)


class TestStartSessionPersistsLatestClassification:
    @pytest.mark.asyncio
    async def test_start_session_persists_latest_classification_when_present(
        self,
        session_repo: SessionRepository,
        conv_repo: ConversationRepository,
        mock_catalog: MagicMock,
    ) -> None:
        async def _process_turn(request):  # type: ignore[no-untyped-def]
            classification = _make_classification(request.session_id)
            if request.session is not None:
                request.session.latest_classification = classification
            return {
                "status": "awaiting_input",
                "question": "What is your use case?",
                "extracted": _make_extraction(),
                "classification": classification,
                "slots": {},
            }

        flow = MagicMock()
        flow.process_turn = AsyncMock(side_effect=_process_turn)

        from api.routers.session import start_session
        from api.schemas.request import StartSessionRequest

        body = StartSessionRequest(message="I need HR")
        response = await start_session(
            body=body,
            session_repo=session_repo,
            conv_repo=conv_repo,
            flow=flow,
            catalog=mock_catalog,
        )

        saved = session_repo.get(response.session_id)
        assert saved.latest_classification is not None
        assert saved.latest_classification.selected_bundle is not None
        assert saved.latest_classification.selected_bundle.bundle_key == "hr_management"

    @pytest.mark.asyncio
    async def test_start_session_latest_classification_none_when_no_suggestions(
        self,
        session_repo: SessionRepository,
        conv_repo: ConversationRepository,
        mock_catalog: MagicMock,
    ) -> None:
        flow = MagicMock()
        flow.process_turn = AsyncMock(
            return_value={
                "status": "awaiting_input",
                "question": "What do you need?",
                "extracted": _make_extraction(),
                "slots": {},
            }
        )

        from api.routers.session import start_session
        from api.schemas.request import StartSessionRequest

        body = StartSessionRequest(message="I need something")
        response = await start_session(
            body=body,
            session_repo=session_repo,
            conv_repo=conv_repo,
            flow=flow,
            catalog=mock_catalog,
        )

        saved = session_repo.get(response.session_id)
        assert saved.latest_classification is None


class TestReplySessionPersistsLatestClassification:
    @pytest.mark.asyncio
    async def test_reply_persists_latest_classification_when_present(
        self,
        session_repo: SessionRepository,
        conv_repo: ConversationRepository,
    ) -> None:
        async def _process_turn(request):  # type: ignore[no-untyped-def]
            classification = _make_classification(request.session_id)
            if request.session is not None:
                request.session.latest_classification = classification
            return {
                "status": "pending_confirmation",
                "message": "I recommend HR Management.",
                "bundle_key": "hr_management",
                "extracted": _make_extraction(),
                "classification": classification,
                "slots": {},
            }

        flow = MagicMock()
        flow.process_turn = AsyncMock(side_effect=_process_turn)

        session = Session(session_id="sess-lc")
        session_repo.save(session)
        conv_repo.append_message(
            "sess-lc", ConversationMessage(role="user", content="initial")
        )

        from api.routers.session import reply_to_session
        from api.schemas.request import ReplyRequest

        body = ReplyRequest(message="Tell me more")
        await reply_to_session(
            session_id="sess-lc",
            body=body,
            session_repo=session_repo,
            conv_repo=conv_repo,
            flow=flow,
        )

        saved = session_repo.get("sess-lc")
        assert saved.latest_classification is not None
        assert saved.latest_classification.selected_bundle is not None
        assert saved.latest_classification.selected_bundle.bundle_key == "hr_management"


class TestReplySessionForwardsPreselectedIntent:
    @pytest.mark.asyncio
    async def test_reply_forwards_session_preselected_intent_to_flow(
        self,
        session_repo: SessionRepository,
        conv_repo: ConversationRepository,
        mock_flow: MagicMock,
    ) -> None:
        session = Session(
            session_id="sess-intent",
            preselected_intent="manage employees",
        )
        session_repo.save(session)
        conv_repo.append_message(
            "sess-intent", ConversationMessage(role="user", content="initial")
        )

        from api.routers.session import reply_to_session
        from api.schemas.request import ReplyRequest

        body = ReplyRequest(message="More about HR")
        await reply_to_session(
            session_id="sess-intent",
            body=body,
            session_repo=session_repo,
            conv_repo=conv_repo,
            flow=mock_flow,
        )

        request_arg = mock_flow.process_turn.call_args.args[0]
        assert request_arg.session.preselected_intent == "manage employees"

    @pytest.mark.asyncio
    async def test_reply_forwards_none_intent_when_not_stored_on_session(
        self,
        session_repo: SessionRepository,
        conv_repo: ConversationRepository,
        mock_flow: MagicMock,
    ) -> None:
        session = Session(session_id="sess-no-intent")
        session_repo.save(session)
        conv_repo.append_message(
            "sess-no-intent", ConversationMessage(role="user", content="initial")
        )

        from api.routers.session import reply_to_session
        from api.schemas.request import ReplyRequest

        body = ReplyRequest(message="More info")
        await reply_to_session(
            session_id="sess-no-intent",
            body=body,
            session_repo=session_repo,
            conv_repo=conv_repo,
            flow=mock_flow,
        )

        request_arg = mock_flow.process_turn.call_args.args[0]
        assert request_arg.session.preselected_intent is None


class TestReplySessionForwardsPreselectedBundleKey:
    @pytest.mark.asyncio
    async def test_reply_forwards_preselected_bundle_key_to_flow(
        self,
        session_repo: SessionRepository,
        conv_repo: ConversationRepository,
        mock_flow: MagicMock,
    ) -> None:
        session = Session(
            session_id="sess-pbk",
            preselected_bundle_key=_VALID_BUNDLE_KEY,
        )
        session_repo.save(session)
        conv_repo.append_message(
            "sess-pbk", ConversationMessage(role="user", content="initial")
        )

        from api.routers.session import reply_to_session
        from api.schemas.request import ReplyRequest

        body = ReplyRequest(message="More about HR")
        await reply_to_session(
            session_id="sess-pbk",
            body=body,
            session_repo=session_repo,
            conv_repo=conv_repo,
            flow=mock_flow,
        )

        request_arg = mock_flow.process_turn.call_args.args[0]
        assert request_arg.session.preselected_bundle_key == _VALID_BUNDLE_KEY

    @pytest.mark.asyncio
    async def test_reply_forwards_none_bundle_key_when_not_preselected(
        self,
        session_repo: SessionRepository,
        conv_repo: ConversationRepository,
        mock_flow: MagicMock,
    ) -> None:
        session = Session(session_id="sess-no-pbk")
        session_repo.save(session)
        conv_repo.append_message(
            "sess-no-pbk", ConversationMessage(role="user", content="initial")
        )

        from api.routers.session import reply_to_session
        from api.schemas.request import ReplyRequest

        body = ReplyRequest(message="More info")
        await reply_to_session(
            session_id="sess-no-pbk",
            body=body,
            session_repo=session_repo,
            conv_repo=conv_repo,
            flow=mock_flow,
        )

        request_arg = mock_flow.process_turn.call_args.args[0]
        assert request_arg.session.preselected_bundle_key is None

    @pytest.mark.asyncio
    async def test_start_session_persists_preselected_bundle_key_on_session(
        self,
        session_repo: SessionRepository,
        conv_repo: ConversationRepository,
        mock_flow: MagicMock,
        mock_catalog: MagicMock,
    ) -> None:
        from api.routers.session import start_session
        from api.schemas.request import StartSessionRequest

        body = StartSessionRequest(
            message="Build me an HR app",
            preselected_bundle_key=_VALID_BUNDLE_KEY,
        )

        response = await start_session(
            body=body,
            session_repo=session_repo,
            conv_repo=conv_repo,
            flow=mock_flow,
            catalog=mock_catalog,
        )

        saved = session_repo.get(response.session_id)
        assert saved.preselected_bundle_key == _VALID_BUNDLE_KEY


class TestStartSessionCaseInsensitiveIntent:
    @pytest.mark.asyncio
    async def test_mixed_case_preselected_intent_is_accepted(
        self,
        session_repo: SessionRepository,
        conv_repo: ConversationRepository,
        mock_flow: MagicMock,
        mock_catalog: MagicMock,
    ) -> None:
        from api.routers.session import start_session
        from api.schemas.request import StartSessionRequest

        body = StartSessionRequest(
            message="Build me an HR app",
            preselected_intent="Manage Employees",
        )

        response = await start_session(
            body=body,
            session_repo=session_repo,
            conv_repo=conv_repo,
            flow=mock_flow,
            catalog=mock_catalog,
        )

        assert response.session_id is not None

    @pytest.mark.asyncio
    async def test_uppercased_intent_is_stored_as_lowercase(
        self,
        session_repo: SessionRepository,
        conv_repo: ConversationRepository,
        mock_flow: MagicMock,
        mock_catalog: MagicMock,
    ) -> None:
        from api.routers.session import start_session
        from api.schemas.request import StartSessionRequest

        body = StartSessionRequest(
            message="Build me an HR app",
            preselected_intent="MANAGE EMPLOYEES",
        )

        response = await start_session(
            body=body,
            session_repo=session_repo,
            conv_repo=conv_repo,
            flow=mock_flow,
            catalog=mock_catalog,
        )

        saved = session_repo.get(response.session_id)
        assert saved.preselected_intent == "manage employees"
