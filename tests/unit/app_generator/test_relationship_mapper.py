"""Unit tests for config_assembly.relationship_mapper.

Covers:
  - _last_token:         token extraction from underscore-delimited keys
  - _infer_relation_type: child-token inference (has_many, belongs_to, references)
  - _make_label:          human-readable label construction and key-fallback paths
  - map_relationships:    pair count, type correctness, model field population,
                          edge inputs (empty, single entity), bundle_key isolation
"""

from __future__ import annotations

import pytest

from agents.app_generator.config_assembly.relationship_mapper import (
    _CHILD_TOKENS,
    _infer_relation_type,
    _last_token,
    _make_label,
    map_relationships,
)
from agents.app_generator.schemas import EntityRelationship
from domain.models.bundle_metadata import EntityDefinition


# ---------------------------------------------------------------------------
# Fixtures / shared helpers
# ---------------------------------------------------------------------------


def _def(label: str, plural: str) -> EntityDefinition:
    """Shorthand EntityDefinition constructor."""
    return EntityDefinition(label=label, plural=plural)


# HR Hub entity set — canonical real-world fixture
HR_ENTITY_DEFS: dict[str, EntityDefinition] = {
    "employee": _def("Employee", "Employees"),
    "leave_request": _def("Leave Request", "Leave Requests"),
    "department": _def("Department", "Departments"),
}

# Ticketing entity set — all-neutral (no child tokens)
TICKETING_ENTITY_DEFS: dict[str, EntityDefinition] = {
    "ticket": _def("Ticket", "Tickets"),
    "queue": _def("Queue", "Queues"),
    "agent": _def("Agent", "Agents"),
}

# Two-entity minimal fixture
TWO_ENTITY_DEFS: dict[str, EntityDefinition] = {
    "project": _def("Project", "Projects"),
    "task": _def("Task", "Tasks"),
}


# ===========================================================================
# _last_token
# ===========================================================================


class TestLastToken:
    def test_last_token_single_word_returns_word(self) -> None:
        assert _last_token("employee") == "employee"

    def test_last_token_two_part_key_returns_suffix(self) -> None:
        assert _last_token("leave_request") == "request"

    def test_last_token_three_part_key_returns_last_segment(self) -> None:
        assert _last_token("work_order_item") == "item"

    def test_last_token_child_suffix_preserved(self) -> None:
        for token in _CHILD_TOKENS:
            assert _last_token(f"some_{token}") == token

    def test_last_token_no_underscore_is_identity(self) -> None:
        assert _last_token("ticket") == "ticket"


# ===========================================================================
# _infer_relation_type
# ===========================================================================


class TestInferRelationType:

    # --- target is a child entity → source has_many target ---------------

    @pytest.mark.parametrize("child_token", sorted(_CHILD_TOKENS))
    def test_infer_has_many_when_target_ends_with_child_token(
        self, child_token: str
    ) -> None:
        assert _infer_relation_type("employee", f"leave_{child_token}") == "has_many"

    def test_infer_has_many_when_target_is_bare_child_token(self) -> None:
        # target key IS the child token with no prefix
        assert _infer_relation_type("queue", "task") == "has_many"

    # --- source is a child entity → source belongs_to target -------------

    @pytest.mark.parametrize("child_token", sorted(_CHILD_TOKENS))
    def test_infer_belongs_to_when_source_ends_with_child_token(
        self, child_token: str
    ) -> None:
        # target is neutral so source's child suffix fires
        assert (
            _infer_relation_type(f"leave_{child_token}", "employee") == "belongs_to"
        )

    # --- target wins when both source and target are child entities -------

    def test_infer_has_many_when_both_are_child_entities(self) -> None:
        # target token takes priority over source token
        assert _infer_relation_type("leave_request", "work_order") == "has_many"

    # --- neither is a child entity → references --------------------------

    def test_infer_references_when_neither_is_child_entity(self) -> None:
        assert _infer_relation_type("employee", "department") == "references"

    def test_infer_references_for_all_neutral_pairs(self) -> None:
        assert _infer_relation_type("ticket", "queue") == "references"
        assert _infer_relation_type("queue", "agent") == "references"
        assert _infer_relation_type("agent", "ticket") == "references"


# ===========================================================================
# _make_label
# ===========================================================================


class TestMakeLabel:
    def test_make_label_has_many_uses_plural_of_target(self) -> None:
        label = _make_label("employee", "leave_request", "has_many", HR_ENTITY_DEFS)
        assert label == "Employee has many Leave Requests"

    def test_make_label_belongs_to_uses_singular_of_target(self) -> None:
        label = _make_label("leave_request", "employee", "belongs_to", HR_ENTITY_DEFS)
        assert label == "Leave Request belongs to Employee"

    def test_make_label_references_uses_label_of_target(self) -> None:
        label = _make_label("employee", "department", "references", HR_ENTITY_DEFS)
        assert label == "Employee references Department"

    def test_make_label_falls_back_to_title_case_when_source_missing(self) -> None:
        # source key not in entity_defs → title-cased key string
        label = _make_label("unknown_entity", "department", "references", HR_ENTITY_DEFS)
        assert label == "Unknown Entity references Department"

    def test_make_label_falls_back_to_title_case_when_target_missing(self) -> None:
        # target key not in entity_defs → title-cased key + "s" for plural
        label = _make_label("employee", "unknown_entity", "has_many", HR_ENTITY_DEFS)
        assert label == "Employee has many Unknown Entitys"

    def test_make_label_both_keys_missing_uses_title_case_fallback(self) -> None:
        label = _make_label("foo_bar", "baz_qux", "references", {})
        assert label == "Foo Bar references Baz Qux"


# ===========================================================================
# map_relationships
# ===========================================================================


class TestMapRelationships:

    # --- guard conditions -------------------------------------------------

    def test_map_relationships_empty_input_returns_empty_list(self) -> None:
        assert map_relationships("hr_hub", {}) == []

    def test_map_relationships_single_entity_returns_empty_list(self) -> None:
        result = map_relationships("hr_hub", {"employee": _def("Employee", "Employees")})
        assert result == []

    # --- pair count -------------------------------------------------------

    def test_map_relationships_two_entities_produces_two_results(self) -> None:
        result = map_relationships("project_mgmt", TWO_ENTITY_DEFS)
        assert len(result) == 2  # 2 * (2-1) = 2 ordered pairs

    def test_map_relationships_three_entities_produces_six_results(self) -> None:
        result = map_relationships("hr_hub", HR_ENTITY_DEFS)
        assert len(result) == 6  # 3 * (3-1) = 6 ordered pairs

    def test_map_relationships_count_equals_n_times_n_minus_one(self) -> None:
        four_entities = {
            "a": _def("A", "As"),
            "b": _def("B", "Bs"),
            "c": _def("C", "Cs"),
            "d": _def("D", "Ds"),
        }
        result = map_relationships("generic", four_entities)
        assert len(result) == 4 * 3  # 12

    # --- no self-references -----------------------------------------------

    def test_map_relationships_no_self_reference_pairs(self) -> None:
        result = map_relationships("hr_hub", HR_ENTITY_DEFS)
        for rel in result:
            assert rel.source_entity != rel.target_entity

    # --- each ordered pair appears exactly once ---------------------------

    def test_map_relationships_each_ordered_pair_appears_once(self) -> None:
        result = map_relationships("hr_hub", HR_ENTITY_DEFS)
        pairs = [(r.source_entity, r.target_entity) for r in result]
        assert len(pairs) == len(set(pairs))

    # --- EntityRelationship field population -----------------------------

    def test_map_relationships_returns_entity_relationship_instances(self) -> None:
        result = map_relationships("hr_hub", HR_ENTITY_DEFS)
        assert all(isinstance(r, EntityRelationship) for r in result)

    def test_map_relationships_all_labels_are_non_empty_strings(self) -> None:
        result = map_relationships("hr_hub", HR_ENTITY_DEFS)
        for rel in result:
            assert isinstance(rel.label, str) and rel.label.strip()

    def test_map_relationships_relation_type_values_are_valid(self) -> None:
        valid_types = {"has_many", "belongs_to", "references"}
        result = map_relationships("hr_hub", HR_ENTITY_DEFS)
        for rel in result:
            assert rel.relation_type in valid_types

    # --- HR Hub specific type assertions ---------------------------------

    def test_map_relationships_hr_hub_employee_has_many_leave_requests(self) -> None:
        result = map_relationships("hr_hub", HR_ENTITY_DEFS)
        rel = _find(result, "employee", "leave_request")
        assert rel is not None
        assert rel.relation_type == "has_many"

    def test_map_relationships_hr_hub_leave_request_belongs_to_employee(self) -> None:
        result = map_relationships("hr_hub", HR_ENTITY_DEFS)
        rel = _find(result, "leave_request", "employee")
        assert rel is not None
        assert rel.relation_type == "belongs_to"

    def test_map_relationships_hr_hub_employee_references_department(self) -> None:
        result = map_relationships("hr_hub", HR_ENTITY_DEFS)
        rel = _find(result, "employee", "department")
        assert rel is not None
        assert rel.relation_type == "references"

    def test_map_relationships_hr_hub_department_has_many_leave_requests(self) -> None:
        result = map_relationships("hr_hub", HR_ENTITY_DEFS)
        rel = _find(result, "department", "leave_request")
        assert rel is not None
        assert rel.relation_type == "has_many"

    def test_map_relationships_hr_hub_leave_request_belongs_to_department(self) -> None:
        result = map_relationships("hr_hub", HR_ENTITY_DEFS)
        rel = _find(result, "leave_request", "department")
        assert rel is not None
        assert rel.relation_type == "belongs_to"

    # --- all-neutral entity set (ticketing) ------------------------------

    def test_map_relationships_all_neutral_entities_are_references(self) -> None:
        result = map_relationships("ticketing", TICKETING_ENTITY_DEFS)
        assert all(r.relation_type == "references" for r in result)

    # --- bundle_key isolation (same entities, different key → same output) -

    def test_map_relationships_bundle_key_does_not_affect_output(self) -> None:
        result_a = map_relationships("hr_hub", HR_ENTITY_DEFS)
        result_b = map_relationships("generic", HR_ENTITY_DEFS)
        pairs_a = {(r.source_entity, r.target_entity, r.relation_type) for r in result_a}
        pairs_b = {(r.source_entity, r.target_entity, r.relation_type) for r in result_b}
        assert pairs_a == pairs_b

    # --- HR Hub label content spot-checks --------------------------------

    def test_map_relationships_hr_hub_has_many_label_uses_plural(self) -> None:
        result = map_relationships("hr_hub", HR_ENTITY_DEFS)
        rel = _find(result, "employee", "leave_request")
        assert rel is not None
        assert rel.label == "Employee has many Leave Requests"

    def test_map_relationships_hr_hub_belongs_to_label_uses_singular(self) -> None:
        result = map_relationships("hr_hub", HR_ENTITY_DEFS)
        rel = _find(result, "leave_request", "employee")
        assert rel is not None
        assert rel.label == "Leave Request belongs to Employee"

    def test_map_relationships_hr_hub_references_label_format(self) -> None:
        result = map_relationships("hr_hub", HR_ENTITY_DEFS)
        rel = _find(result, "employee", "department")
        assert rel is not None
        assert rel.label == "Employee references Department"


# ---------------------------------------------------------------------------
# Private helper
# ---------------------------------------------------------------------------


def _find(
    relationships: list[EntityRelationship],
    source: str,
    target: str,
) -> EntityRelationship | None:
    """Return the first relationship matching (source, target), or None."""
    return next(
        (r for r in relationships if r.source_entity == source and r.target_entity == target),
        None,
    )
