from __future__ import annotations

import pytest

from agents.app_generator.config_assembly.config_encoder import encode_config

# ---------------------------------------------------------------------------
# Fixtures — minimal valid configs per bundle
# ---------------------------------------------------------------------------

_KPI = {"key": "active_headcount", "label": "Active Headcount", "unit": "count"}


def _hr_hub_config() -> dict[str, object]:
    return {
        "ticket_categories": ["leave", "onboarding"],
        "default_statuses": ["open", "in_progress", "resolved"],
        "default_priorities": ["low", "medium", "high"],
        "queue_names": ["Leave Requests", "General HR"],
        "kpi_definitions": [_KPI],
        "permission_services": ["hr_hub", "chat"],
        "landing_pages": [{"service": "hr_hub", "path": "/hr-hub"}],
    }


def _project_mgmt_config() -> dict[str, object]:
    return {
        "task_statuses": ["backlog", "in_progress", "done"],
        "task_priorities": ["low", "high"],
        "milestone_statuses": ["pending", "achieved"],
        "kpi_definitions": [_KPI],
        "permission_services": ["project_mgmt"],
        "landing_pages": [],
    }


def _ticketing_config() -> dict[str, object]:
    return {
        "work_order_statuses": ["pending", "completed"],
        "work_order_priorities": ["low", "emergency"],
        "service_types": ["incident", "maintenance"],
        "kpi_definitions": [_KPI],
        "permission_services": ["ticketing"],
        "landing_pages": [],
    }


def _generic_config() -> dict[str, object]:
    return {
        "ticket_statuses": ["open", "closed"],
        "ticket_priorities": ["low", "high"],
        "kpi_definitions": [_KPI],
        "permission_services": [],
        "landing_pages": [],
    }


# ---------------------------------------------------------------------------
# Happy-path tests — all four bundles
# ---------------------------------------------------------------------------


def test_encode_config_hr_hub_valid() -> None:
    result = encode_config("hr_hub", _hr_hub_config())
    assert result["ticket_categories"] == ["leave", "onboarding"]
    assert result["default_statuses"] == ["open", "in_progress", "resolved"]
    assert result["kpi_definitions"] == [_KPI]


def test_encode_config_project_mgmt_valid() -> None:
    result = encode_config("project_mgmt", _project_mgmt_config())
    assert result["task_statuses"] == ["backlog", "in_progress", "done"]
    assert result["milestone_statuses"] == ["pending", "achieved"]
    assert result["kpi_definitions"] == [_KPI]


def test_encode_config_ticketing_valid() -> None:
    result = encode_config("ticketing", _ticketing_config())
    assert result["work_order_statuses"] == ["pending", "completed"]
    assert result["service_types"] == ["incident", "maintenance"]
    assert result["kpi_definitions"] == [_KPI]


def test_encode_config_generic_valid() -> None:
    result = encode_config("generic", _generic_config())
    assert result["ticket_statuses"] == ["open", "closed"]
    assert result["kpi_definitions"] == [_KPI]


# ---------------------------------------------------------------------------
# Missing key — inserted with empty-list default
# ---------------------------------------------------------------------------


def test_encode_config_missing_key_uses_default() -> None:
    config = _hr_hub_config()
    del config["default_statuses"]
    result = encode_config("hr_hub", config)
    assert result["default_statuses"] == []


# ---------------------------------------------------------------------------
# Wrong type — replaced with empty-list default
# ---------------------------------------------------------------------------


def test_encode_config_wrong_type_uses_default() -> None:
    config = _hr_hub_config()
    config["kpi_definitions"] = "not-a-list"  # type: ignore[assignment]
    result = encode_config("hr_hub", config)
    assert result["kpi_definitions"] == []


# ---------------------------------------------------------------------------
# String-list normalisation — deduplication and whitespace stripping
# ---------------------------------------------------------------------------


def test_encode_config_str_list_deduplication() -> None:
    config = _hr_hub_config()
    config["default_statuses"] = ["open", "in_progress", "open", "resolved"]
    result = encode_config("hr_hub", config)
    assert result["default_statuses"] == ["open", "in_progress", "resolved"]


def test_encode_config_str_list_strips_whitespace() -> None:
    config = _hr_hub_config()
    config["default_statuses"] = ["  open  ", "in_progress ", " resolved"]
    result = encode_config("hr_hub", config)
    assert result["default_statuses"] == ["open", "in_progress", "resolved"]


def test_encode_config_str_list_dedup_after_strip() -> None:
    """Strings that are equal after stripping should be deduplicated."""
    config = _hr_hub_config()
    config["default_statuses"] = ["open", " open", "open "]
    result = encode_config("hr_hub", config)
    assert result["default_statuses"] == ["open"]


# ---------------------------------------------------------------------------
# kpi_definitions normalisation
# ---------------------------------------------------------------------------


def test_encode_config_kpi_definitions_filters_incomplete() -> None:
    """Items missing required fields are dropped."""
    config = _hr_hub_config()
    config["kpi_definitions"] = [
        {"key": "k1", "label": "K1"},                          # missing unit
        {"key": "k2", "label": "K2", "unit": "count"},         # valid
        {"label": "K3", "unit": "percentage"},                  # missing key
    ]
    result = encode_config("hr_hub", config)
    assert len(result["kpi_definitions"]) == 1  # type: ignore[arg-type]
    assert result["kpi_definitions"][0]["key"] == "k2"  # type: ignore[index]


def test_encode_config_kpi_definitions_valid_passthrough() -> None:
    """Well-formed kpi_definition items pass through unchanged."""
    config = _hr_hub_config()
    kpis = [
        {"key": "k1", "label": "K One", "unit": "count"},
        {"key": "k2", "label": "K Two", "unit": "percentage"},
    ]
    config["kpi_definitions"] = kpis
    result = encode_config("hr_hub", config)
    assert result["kpi_definitions"] == kpis


def test_encode_config_kpi_definitions_drops_non_dict() -> None:
    """Non-dict items inside kpi_definitions are dropped."""
    config = _hr_hub_config()
    config["kpi_definitions"] = ["not-a-dict", _KPI]
    result = encode_config("hr_hub", config)
    assert result["kpi_definitions"] == [_KPI]


# ---------------------------------------------------------------------------
# Unknown bundle key — warns and returns copy
# ---------------------------------------------------------------------------


def test_encode_config_unknown_bundle_key_warns(caplog: pytest.LogCaptureFixture) -> None:
    config = {"some_key": ["a", "b"]}
    result = encode_config("unknown_bundle", config)
    assert result == config
    assert "unrecognised bundle_key" in caplog.text.lower()


# ---------------------------------------------------------------------------
# Extra keys are preserved (e.g. relationships injected upstream)
# ---------------------------------------------------------------------------


def test_encode_config_extra_keys_preserved() -> None:
    config = _hr_hub_config()
    config["relationships"] = [{"source_entity": "Employee", "target_entity": "Ticket"}]
    result = encode_config("hr_hub", config)
    assert "relationships" in result
    assert result["relationships"] == config["relationships"]


# ---------------------------------------------------------------------------
# Guard-rail: empty / None / invalid preview_config
# ---------------------------------------------------------------------------


def test_encode_config_empty_bundle_key_raises() -> None:
    with pytest.raises(ValueError, match="bundle_key must be a non-empty string"):
        encode_config("", {"key": "value"})


def test_encode_config_whitespace_bundle_key_raises() -> None:
    with pytest.raises(ValueError, match="bundle_key must be a non-empty string"):
        encode_config("   ", {"key": "value"})


def test_encode_config_none_preview_config() -> None:
    result = encode_config("hr_hub", None)  # type: ignore[arg-type]
    assert result == {}


def test_encode_config_empty_preview_config() -> None:
    result = encode_config("hr_hub", {})
    assert result == {}


def test_encode_config_non_dict_preview_config() -> None:
    result = encode_config("hr_hub", ["not", "a", "dict"])  # type: ignore[arg-type]
    assert result == {}
