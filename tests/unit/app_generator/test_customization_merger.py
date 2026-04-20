from __future__ import annotations

from agents.app_generator.config_assembly.customization_merger import (
    _deep_merge,
    extract_customization,
    merge_customization,
)


# ---------------------------------------------------------------------------
# _deep_merge — unit tests
# ---------------------------------------------------------------------------


def test_deep_merge_scalar_override() -> None:
    base = {"a": 1, "b": "old"}
    override = {"b": "new"}
    result = _deep_merge(base, override)
    assert result == {"a": 1, "b": "new"}


def test_deep_merge_list_replaces() -> None:
    base = {"statuses": ["open", "closed"]}
    override = {"statuses": ["pending", "done"]}
    result = _deep_merge(base, override)
    assert result["statuses"] == ["pending", "done"]


def test_deep_merge_nested_dict_recurse() -> None:
    base = {"config": {"a": 1, "b": 2}}
    override = {"config": {"b": 99, "c": 3}}
    result = _deep_merge(base, override)
    assert result["config"] == {"a": 1, "b": 99, "c": 3}


def test_deep_merge_extra_key_in_override_added() -> None:
    base = {"x": 1}
    override = {"y": 2}
    result = _deep_merge(base, override)
    assert result == {"x": 1, "y": 2}


def test_deep_merge_does_not_mutate_base() -> None:
    base: dict[str, object] = {"a": [1, 2, 3]}
    override: dict[str, object] = {"a": [9]}
    _deep_merge(base, override)
    assert base["a"] == [1, 2, 3]


def test_deep_merge_does_not_mutate_override() -> None:
    base: dict[str, object] = {"a": 1}
    override: dict[str, object] = {"b": 2}
    _deep_merge(base, override)
    assert override == {"b": 2}


def test_deep_merge_empty_override_returns_base_copy() -> None:
    base = {"a": 1}
    result = _deep_merge(base, {})
    assert result == base
    assert result is not base


def test_deep_merge_empty_base_returns_override_copy() -> None:
    override = {"a": 1}
    result = _deep_merge({}, override)
    assert result == override


# ---------------------------------------------------------------------------
# extract_customization — unit tests
# ---------------------------------------------------------------------------


def _hr_hub_dummy(queue_names: list[str]) -> dict[str, object]:
    return {
        "bundle_key": "hr_hub",
        "stores": {
            "queues": [{"id": i + 1, "name": n} for i, n in enumerate(queue_names)],
        },
    }


def test_extract_hr_hub_queue_names() -> None:
    dummy = _hr_hub_dummy(["Leave Requests", "Onboarding", "General HR"])
    result = extract_customization(dummy, "hr_hub")
    assert result == {"queue_names": ["Leave Requests", "Onboarding", "General HR"]}


def test_extract_hr_hub_empty_queues_returns_empty() -> None:
    dummy: dict[str, object] = {"bundle_key": "hr_hub", "stores": {"queues": []}}
    assert extract_customization(dummy, "hr_hub") == {}


def test_extract_hr_hub_filters_nameless_queues() -> None:
    dummy: dict[str, object] = {
        "bundle_key": "hr_hub",
        "stores": {
            "queues": [
                {"id": 1, "name": "Valid Queue"},
                {"id": 2},                   # missing name
                {"id": 3, "name": "   "},    # blank name
            ]
        },
    }
    result = extract_customization(dummy, "hr_hub")
    assert result == {"queue_names": ["Valid Queue"]}


def test_extract_hr_hub_missing_stores_returns_empty() -> None:
    dummy: dict[str, object] = {"bundle_key": "hr_hub"}
    assert extract_customization(dummy, "hr_hub") == {}


def test_extract_hr_hub_non_dict_stores_returns_empty() -> None:
    dummy: dict[str, object] = {"bundle_key": "hr_hub", "stores": "bad"}
    assert extract_customization(dummy, "hr_hub") == {}


def test_extract_project_mgmt_returns_empty() -> None:
    dummy: dict[str, object] = {"bundle_key": "project_mgmt", "stores": {"tasks": []}}
    assert extract_customization(dummy, "project_mgmt") == {}


def test_extract_ticketing_returns_empty() -> None:
    dummy: dict[str, object] = {"bundle_key": "ticketing", "stores": {"tickets": []}}
    assert extract_customization(dummy, "ticketing") == {}


def test_extract_generic_returns_empty() -> None:
    dummy: dict[str, object] = {"bundle_key": "generic", "stores": {}}
    assert extract_customization(dummy, "generic") == {}


def test_extract_unknown_bundle_returns_empty() -> None:
    dummy: dict[str, object] = {"bundle_key": "unknown", "stores": {}}
    assert extract_customization(dummy, "unknown") == {}


# ---------------------------------------------------------------------------
# merge_customization — public API
# ---------------------------------------------------------------------------


def test_merge_customization_empty_customization_returns_copy() -> None:
    base = {"queue_names": ["A", "B"], "statuses": ["open"]}
    result = merge_customization(base, {})
    assert result == base
    assert result is not base


def test_merge_customization_applies_override() -> None:
    base: dict[str, object] = {
        "queue_names": ["Leave Requests", "General HR"],
        "default_statuses": ["open", "closed"],
    }
    customization: dict[str, object] = {"queue_names": ["Engineering", "Operations"]}
    result = merge_customization(base, customization)
    assert result["queue_names"] == ["Engineering", "Operations"]
    assert result["default_statuses"] == ["open", "closed"]


def test_merge_customization_does_not_mutate_base() -> None:
    base: dict[str, object] = {"queue_names": ["A"]}
    customization: dict[str, object] = {"queue_names": ["B"]}
    merge_customization(base, customization)
    assert base["queue_names"] == ["A"]


def test_merge_customization_end_to_end_hr_hub() -> None:
    """Queue names from dummy data stores flow into the merged config."""
    base_config: dict[str, object] = {
        "queue_names": ["Leave Requests", "General HR"],
        "default_statuses": ["open", "resolved"],
    }
    dummy_data = _hr_hub_dummy(["Engineering", "Operations"])
    customization = extract_customization(dummy_data, "hr_hub")
    result = merge_customization(base_config, customization)
    assert result["queue_names"] == ["Engineering", "Operations"]
    assert result["default_statuses"] == ["open", "resolved"]
