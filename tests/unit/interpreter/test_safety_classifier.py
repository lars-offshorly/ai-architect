from __future__ import annotations

import asyncio

from agents.interpreter.safety_classifier import SafetyClassifier


def test_knit_workspace_request_is_in_scope_allow() -> None:
    classifier = SafetyClassifier(model=None)
    decision = asyncio.run(
        classifier.classify("s1", "Create a knit workspace for me")
    )
    assert decision.label == "allow"


def test_software_build_request_is_outside_scope() -> None:
    classifier = SafetyClassifier(model=None)
    decision = asyncio.run(classifier.classify("s2", "Write code for my backend"))
    assert decision.label == "outside_scope"


class _FailIfCalledModel:
    def with_structured_output(self, *_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("LLM safety should not be called for low-risk follow-up")


def test_low_risk_followup_bypasses_llm_and_allows() -> None:
    classifier = SafetyClassifier(model=_FailIfCalledModel())  # type: ignore[arg-type]
    decision = asyncio.run(classifier.classify("s3", "Equip"))
    assert decision.label == "allow"


def test_short_risky_token_not_auto_allowed() -> None:
    classifier = SafetyClassifier(model=None)
    decision = asyncio.run(classifier.classify("s4", "password"))
    assert decision.label != "allow"


def test_change_to_industry_followup_is_in_scope_allow() -> None:
    classifier = SafetyClassifier(model=None)
    decision = asyncio.run(classifier.classify("s5", "Change to HR agency"))
    assert decision.label == "allow"
