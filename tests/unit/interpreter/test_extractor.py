from __future__ import annotations

# pylint: disable=duplicate-code
from agents.interpreter.extractor import (
    _build_extraction_context,
    _build_synonym_index,
    _normalize_keywords,
)
from catalog.bundle_catalog import BundleDefinition
from domain.models.conversation import ConversationMessage
from domain.models.extracted_info import ExtractedInfo


class TestExtractedInfoContractFrozen:
    """ExtractedInfo must not grow new fields — AD-1."""

    def test_defaults(self) -> None:
        info = ExtractedInfo(session_id="s1")
        assert info.company_name is None
        assert info.employee_names == []
        assert info.slots == {}

    def test_with_values(self) -> None:
        info = ExtractedInfo(
            session_id="s1",
            company_name="Acme",
            industry_hint="healthcare",
            employee_names=["Jane"],
            slots={"team_size": 50},
        )
        assert info.company_name == "Acme"
        assert info.slots["team_size"] == 50


class TestExtractorContextBuilder:
    """Tests for the static context-building helper used inside Extractor."""

    def test_build_context_includes_user_message(self) -> None:
        ctx = _build_extraction_context(
            user_message="I need an HR system",
            summary="",
            history=[],
        )
        assert "I need an HR system" in ctx

    def test_build_context_includes_summary_when_present(self) -> None:
        ctx = _build_extraction_context(
            user_message="Latest message",
            summary="User wants to track employees",
            history=[],
        )
        assert "User wants to track employees" in ctx
        assert "Latest message" in ctx

    def test_build_context_includes_recent_history(self) -> None:
        history = [
            ConversationMessage(role="user", content="We have 50 employees"),
            ConversationMessage(role="assistant", content="Got it."),
        ]
        ctx = _build_extraction_context(
            user_message="And we need leave tracking",
            summary="",
            history=history,
        )
        assert "We have 50 employees" in ctx
        assert "And we need leave tracking" in ctx

    def test_build_context_limits_history_to_last_five(self) -> None:
        history = [
            ConversationMessage(role="user", content=f"msg {i}") for i in range(10)
        ]
        ctx = _build_extraction_context(
            user_message="latest",
            summary="",
            history=history,
        )
        assert "msg 9" in ctx
        assert "msg 5" in ctx
        assert "msg 0" not in ctx


class TestExtractorSynonymNormalization:
    """Tests for synonym normalization against BundleDefinition list."""

    def test_normalize_keywords_exact_match_maps_to_canonical_synonym(self) -> None:
        bundles = [
            BundleDefinition(
                bundle_key="hr_management",
                render_key="hr_hub",
                display_name="HR Management",
                primary_entity="people",
                description="HR bundle",
                template_dir="hr_management",
                synonyms=["human resources", "people ops"],
                typical_entities=["employee"],
                typical_intents=[],
                required_signals=["employee workflow"],
            )
        ]
        exact_index, phrase_index = _build_synonym_index(bundles)
        normalized = _normalize_keywords(
            ["Human Resources", "projects"], exact_index, phrase_index
        )
        assert "human resources" in normalized

    def test_normalize_keywords_phrase_match_prefers_longest_synonym(self) -> None:
        bundles = [
            BundleDefinition(
                bundle_key="ticketing",
                render_key="ticketing",
                display_name="Ticketing",
                primary_entity="ticket",
                description="Ticket bundle",
                template_dir="ticketing",
                synonyms=["desk", "service desk", "help desk"],
                typical_entities=["ticket"],
                typical_intents=[],
                required_signals=["ticket workflow"],
            )
        ]
        exact_index, phrase_index = _build_synonym_index(bundles)
        normalized = _normalize_keywords(
            ["Enterprise Service Desk Setup"], exact_index, phrase_index
        )
        assert normalized == ["service desk"]

    def test_normalize_keywords_preserves_unmatched_terms(self) -> None:
        bundles = [
            BundleDefinition(
                bundle_key="hr_management",
                render_key="hr_hub",
                display_name="HR Management",
                primary_entity="people",
                description="HR bundle",
                template_dir="hr_management",
                synonyms=["human resources"],
                typical_entities=["employee"],
                typical_intents=[],
                required_signals=["employee workflow"],
            )
        ]
        exact_index, phrase_index = _build_synonym_index(bundles)
        normalized = _normalize_keywords(
            ["payroll system", "hr"], exact_index, phrase_index
        )
        assert "payroll system" in normalized
        assert "hr" in normalized

    def test_normalize_keywords_casefold_deduplicates_final_values(self) -> None:
        bundles = [
            BundleDefinition(
                bundle_key="hr_management",
                render_key="hr_hub",
                display_name="HR Management",
                primary_entity="people",
                description="HR bundle",
                template_dir="hr_management",
                synonyms=["human resources"],
                typical_entities=["employee"],
                typical_intents=[],
                required_signals=["employee workflow"],
            )
        ]
        exact_index, phrase_index = _build_synonym_index(bundles)
        normalized = _normalize_keywords(
            ["human resources", "Human Resources"], exact_index, phrase_index
        )
        assert normalized == ["human resources"]
