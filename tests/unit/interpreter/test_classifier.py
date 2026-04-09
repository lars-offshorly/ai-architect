from __future__ import annotations

# pylint: disable=duplicate-code
from typing import cast

from agents.interpreter.rules import apply_rule_boosts, detect_signals
from catalog.bundle_catalog import BundleDefinition


def _hr_bundle() -> BundleDefinition:
    return BundleDefinition(
        bundle_key="hr_management",
        render_key="hr_hub",
        display_name="HR Management",
        primary_entity="people",
        description="HR bundle",
        template_dir="hr_management",
        synonyms=["human resources", "people ops", "HR"],
        typical_entities=["employee", "manager", "leave request"],
        typical_intents=["manage employees", "approve leave"],
        required_signals=["employee workflow"],
        signal_boosts={"hr": 0.20, "employee": 0.10, "leave": 0.15, "onboarding": 0.15},
    )


def _project_bundle() -> BundleDefinition:
    return BundleDefinition(
        bundle_key="project_mgmt",
        render_key="project_mgmt",
        display_name="Project Management",
        primary_entity="project",
        description="Project bundle",
        template_dir="project_mgmt",
        synonyms=["project tracker", "task manager"],
        typical_entities=["project", "milestone", "task"],
        typical_intents=["track projects", "manage milestones"],
        required_signals=["project workflow"],
        signal_boosts={"project": 0.15, "milestone": 0.15, "sprint": 0.20},
    )


def _confidence(candidate: dict[str, object]) -> float:
    return cast(float, candidate["confidence"])


def test_detect_signals_finds_hr_terms() -> None:
    bundles = [_hr_bundle()]
    signals = detect_signals(
        ["We need to manage employee leave requests and onboarding"], bundles
    )
    assert "employee" in signals
    assert "leave request" in signals


def test_detect_signals_finds_project_terms() -> None:
    bundles = [_project_bundle()]
    signals = detect_signals(
        ["We work on projects with milestones and sprints"], bundles
    )
    assert "project" in signals
    assert "milestone" in signals


def test_detect_signals_matches_synonyms() -> None:
    bundles = [_hr_bundle()]
    signals = detect_signals(["We need a human resources tracking system"], bundles)
    assert "human resources" in signals


def test_detect_signals_empty_text() -> None:
    signals = detect_signals([], [_hr_bundle()])
    assert not signals


def test_detect_signals_empty_bundles() -> None:
    signals = detect_signals(["employee leave request"], [])
    assert not signals


def test_apply_rule_boosts_increases_confidence() -> None:
    bundles = [_hr_bundle()]
    candidates = [
        {
            "bundle_key": "hr_management",
            "display_name": "HR Management",
            "confidence": 0.5,
            "reasoning": "",
            "matched_signals": [],
        },
    ]
    result = apply_rule_boosts(candidates, bundles, ["leave", "hr"])
    assert _confidence(result[0]) > 0.5


def test_apply_rule_boosts_caps_at_one() -> None:
    bundles = [_hr_bundle()]
    candidates = [
        {
            "bundle_key": "hr_management",
            "display_name": "HR Management",
            "confidence": 0.95,
            "reasoning": "",
            "matched_signals": [],
        },
    ]
    result = apply_rule_boosts(
        candidates, bundles, ["leave", "hr", "employee", "onboarding"]
    )
    assert _confidence(result[0]) <= 1.0


def test_apply_rule_boosts_no_signals_no_change() -> None:
    bundles = [_hr_bundle()]
    candidates = [
        {
            "bundle_key": "hr_management",
            "display_name": "HR Management",
            "confidence": 0.5,
            "reasoning": "",
            "matched_signals": [],
        },
    ]
    result = apply_rule_boosts(candidates, bundles, [])
    assert _confidence(result[0]) == 0.5


def test_apply_rule_boosts_only_affects_matching_bundle() -> None:
    bundles = [_hr_bundle(), _project_bundle()]
    candidates = [
        {
            "bundle_key": "hr_management",
            "confidence": 0.5,
            "reasoning": "",
            "matched_signals": [],
        },
        {
            "bundle_key": "project_mgmt",
            "confidence": 0.5,
            "reasoning": "",
            "matched_signals": [],
        },
    ]
    result = apply_rule_boosts(candidates, bundles, ["hr"])
    hr_result = next(c for c in result if c["bundle_key"] == "hr_management")
    proj_result = next(c for c in result if c["bundle_key"] == "project_mgmt")
    assert _confidence(hr_result) > 0.5
    assert _confidence(proj_result) == 0.5
