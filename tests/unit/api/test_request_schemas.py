"""Unit tests for request schemas — Phase 1 optional field extensions."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from api.schemas.request import ReplyRequest, StartSessionRequest


class TestStartSessionRequestBackwardCompatibility:
    def test_existing_client_with_message_only(self) -> None:
        req = StartSessionRequest(message="Build an HR system")
        assert req.message == "Build an HR system"
        assert req.user_id is None
        assert req.preselected_bundle_key is None
        assert req.preselected_intent is None

    def test_existing_client_with_user_id(self) -> None:
        req = StartSessionRequest(message="Build an HR system", user_id="u1")
        assert req.user_id == "u1"
        assert req.preselected_bundle_key is None
        assert req.preselected_intent is None

    def test_empty_message_rejected(self) -> None:
        with pytest.raises(ValidationError):
            StartSessionRequest(message="")


class TestStartSessionRequestNewFields:
    def test_preselected_bundle_key_accepted(self) -> None:
        req = StartSessionRequest(
            message="Build an HR system",
            preselected_bundle_key="hr_management",
        )
        assert req.preselected_bundle_key == "hr_management"
        assert req.preselected_intent is None

    def test_preselected_intent_accepted(self) -> None:
        req = StartSessionRequest(
            message="We need an onboarding system",
            preselected_intent="manage employees",
        )
        assert req.preselected_intent == "manage employees"
        assert req.preselected_bundle_key is None

    def test_both_preselected_fields_accepted(self) -> None:
        req = StartSessionRequest(
            message="Build an HR system",
            preselected_bundle_key="hr_management",
            preselected_intent="manage employees",
        )
        assert req.preselected_bundle_key == "hr_management"
        assert req.preselected_intent == "manage employees"

    def test_none_preselected_bundle_key_serializes_correctly(self) -> None:
        req = StartSessionRequest(message="Build an app")
        data = req.model_dump()
        assert data["preselected_bundle_key"] is None
        assert data["preselected_intent"] is None


class TestReplyRequestBackwardCompatibility:
    def test_existing_client_with_message_only(self) -> None:
        req = ReplyRequest(message="We manage leave requests")
        assert req.message == "We manage leave requests"
        assert req.force_preview is False

    def test_empty_message_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ReplyRequest(message="")


class TestReplyRequestNewFields:
    def test_force_preview_defaults_to_false(self) -> None:
        req = ReplyRequest(message="Tell me more")
        assert req.force_preview is False

    def test_force_preview_can_be_set_true(self) -> None:
        req = ReplyRequest(message="preview now", force_preview=True)
        assert req.force_preview is True

    def test_force_preview_serializes_correctly(self) -> None:
        req = ReplyRequest(message="preview now", force_preview=True)
        data = req.model_dump()
        assert data["force_preview"] is True
