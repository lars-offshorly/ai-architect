from __future__ import annotations

import pytest

from agents.interpreter.rules import apply_rule_boosts, build_signal_boosts, detect_signals


def test_detect_signals_finds_hr_terms() -> None:
    signals = detect_signals("We need to manage employee leave requests and onboarding")
    assert "leave" in signals
    assert "employee" in signals
    assert "onboarding" in signals


def test_detect_signals_finds_project_terms() -> None:
    signals = detect_signals("We work on consulting projects with milestones and sprints")
    assert "project" in signals
    assert "consulting" in signals


def test_detect_signals_empty_text() -> None:
    signals = detect_signals("")
    assert signals == []


def test_apply_rule_boosts_increases_confidence() -> None:
    candidates = [
        {"bundle_key": "hr_hub", "display_name": "HR Hub", "confidence": 0.5, "reasoning": "", "matched_signals": []},
    ]
    boosts = build_signal_boosts()
    result = apply_rule_boosts(candidates, boosts, ["leave", "hr"])
    assert result[0]["confidence"] > 0.5


def test_apply_rule_boosts_caps_at_one() -> None:
    candidates = [
        {"bundle_key": "hr_hub", "display_name": "HR Hub", "confidence": 0.95, "reasoning": "", "matched_signals": []},
    ]
    boosts = build_signal_boosts()
    result = apply_rule_boosts(candidates, boosts, ["leave", "hr", "employee", "onboarding", "people ops"])
    assert result[0]["confidence"] <= 1.0


def test_apply_rule_boosts_no_signals_no_change() -> None:
    candidates = [
        {"bundle_key": "hr_hub", "display_name": "HR Hub", "confidence": 0.5, "reasoning": "", "matched_signals": []},
    ]
    boosts = build_signal_boosts()
    result = apply_rule_boosts(candidates, boosts, [])
    assert result[0]["confidence"] == 0.5
