"""Unit tests for config_assembly.relationship_mapper.

Covers:
  - _resolve_display:   label/plural resolution with and without entity_defs
  - _build_label:       human-readable label construction for all relation types
  - map_relationships:  YAML-driven loading, label auto-generation, label override,
                        output count, field population, and edge inputs
"""

from __future__ import annotations

import pytest

from agents.app_generator.config_assembly.relationship_mapper import (
    _build_label,
    _resolve_display,
    map_relationships,
)
from agents.app_generator.schemas import EntityRelationship
from domain.models.bundle_metadata import EntityDefinition, EntityRelationshipDefinition


# ---------------------------------------------------------------------------
# Fixtures / shared helpers
# ---------------------------------------------------------------------------


def _def(label: str, plural: str) -> EntityDefinition:
    return EntityDefinition(label=label, plural=plural)


def _rel(
    source: str,
    target: str,
    rel_type: str,
    label: str | None = None,
) -> EntityRelationshipDefinition:
    return EntityRelationshipDefinition(source=source, target=target, type=rel_type, label=label)


# HR Hub entity definitions — mirrors bundle_registry.yaml
HR_ENTITY_DEFS: dict[str, EntityDefinition] = {
    "employee": _def("Employee", "Employees"),
    "leave_request": _def("Leave Request", "Leave Requests"),
    "department": _def("Department", "Departments"),
}

# HR Hub explicit relationships — mirrors bundle_registry.yaml entity_relationships
HR_ENTITY_RELS: list[EntityRelationshipDefinition] = [
    _rel("department", "employee", "has_many"),
    _rel("employee", "department", "belongs_to"),
    _rel("employee", "leave_request", "has_many"),
    _rel("leave_request", "employee", "belongs_to"),
]

# Ticketing entity definitions
TICKETING_ENTITY_DEFS: dict[str, EntityDefinition] = {
    "ticket": _def("Ticket", "Tickets"),
    "queue": _def("Queue", "Queues"),
    "agent": _def("Agent", "Agents"),
}

TICKETING_ENTITY_RELS: list[EntityRelationshipDefinition] = [
    _rel("queue", "ticket", "has_many"),
    _rel("ticket", "queue", "belongs_to"),
    _rel("queue", "agent", "has_many"),
    _rel("agent", "ticket", "many_to_many"),
]


# ===========================================================================
# _resolve_display
# ===========================================================================


class TestResolveDisplay:
    def test_returns_label_and_plural_from_entity_defs(self) -> None:
        label, plural = _resolve_display("employee", HR_ENTITY_DEFS)
        assert label == "Employee"
        assert plural == "Employees"

    def test_returns_multi_word_label_correctly(self) -> None:
        label, plural = _resolve_display("leave_request", HR_ENTITY_DEFS)
        assert label == "Leave Request"
        assert plural == "Leave Requests"

    def test_falls_back_to_title_case_when_key_missing(self) -> None:
        label, plural = _resolve_display("unknown_entity", HR_ENTITY_DEFS)
        assert label == "Unknown Entity"
        assert plural == "Unknown Entitys"  # synthetic fallback: label + "s"

    def test_falls_back_on_empty_entity_defs(self) -> None:
        label, plural = _resolve_display("leave_request", {})
        assert label == "Leave Request"
        assert plural == "Leave Requests"

    def test_single_word_key_falls_back_correctly(self) -> None:
        label, plural = _resolve_display("payroll", {})
        assert label == "Payroll"
        assert plural == "Payrolls"


# ===========================================================================
# _build_label
# ===========================================================================


class TestBuildLabel:
    def test_has_many_uses_plural(self) -> None:
        assert _build_label("Department", "Employee", "Employees", "has_many") == (
            "Department has many Employees"
        )

    def test_belongs_to_uses_singular(self) -> None:
        assert _build_label("Employee", "Department", "Departments", "belongs_to") == (
            "Employee belongs to Department"
        )

    def test_many_to_many_format(self) -> None:
        assert _build_label("Agent", "Ticket", "Tickets", "many_to_many") == (
            "Agent and Tickets are many-to-many"
        )

    def test_references_uses_singular(self) -> None:
        assert _build_label("Project", "Team Member", "Team Members", "references") == (
            "Project references Team Member"
        )

    def test_unknown_type_falls_back_to_references_format(self) -> None:
        assert _build_label("A", "B", "Bs", "custom_type") == "A references B"


# ===========================================================================
# map_relationships
# ===========================================================================


class TestMapRelationships:

    # --- guard conditions -------------------------------------------------

    def test_empty_relationships_returns_empty_list(self) -> None:
        assert map_relationships("hr_hub", [], HR_ENTITY_DEFS) == []

    def test_empty_relationships_with_empty_defs_returns_empty_list(self) -> None:
        assert map_relationships("hr_hub", [], {}) == []

    # --- output count matches input --------------------------------------

    def test_output_count_matches_input_count(self) -> None:
        result = map_relationships("hr_hub", HR_ENTITY_RELS, HR_ENTITY_DEFS)
        assert len(result) == len(HR_ENTITY_RELS)

    def test_ticketing_output_count_matches_input(self) -> None:
        result = map_relationships("ticketing", TICKETING_ENTITY_RELS, TICKETING_ENTITY_DEFS)
        assert len(result) == len(TICKETING_ENTITY_RELS)

    # --- EntityRelationship field population ----------------------------

    def test_returns_entity_relationship_instances(self) -> None:
        result = map_relationships("hr_hub", HR_ENTITY_RELS, HR_ENTITY_DEFS)
        assert all(isinstance(r, EntityRelationship) for r in result)

    def test_source_entity_and_target_entity_match_yaml(self) -> None:
        result = map_relationships("hr_hub", HR_ENTITY_RELS, HR_ENTITY_DEFS)
        pairs = [(r.source_entity, r.target_entity) for r in result]
        expected = [(r.source, r.target) for r in HR_ENTITY_RELS]
        assert pairs == expected

    def test_relation_type_matches_yaml(self) -> None:
        result = map_relationships("hr_hub", HR_ENTITY_RELS, HR_ENTITY_DEFS)
        types = [r.relation_type for r in result]
        expected = [r.type for r in HR_ENTITY_RELS]
        assert types == expected

    def test_all_labels_are_non_empty_strings(self) -> None:
        result = map_relationships("hr_hub", HR_ENTITY_RELS, HR_ENTITY_DEFS)
        for rel in result:
            assert isinstance(rel.label, str) and rel.label.strip()

    # --- HR Hub specific type and label assertions ----------------------

    def test_hr_hub_department_has_many_employees(self) -> None:
        result = map_relationships("hr_hub", HR_ENTITY_RELS, HR_ENTITY_DEFS)
        rel = _find(result, "department", "employee")
        assert rel is not None
        assert rel.relation_type == "has_many"
        assert rel.label == "Department has many Employees"

    def test_hr_hub_employee_belongs_to_department(self) -> None:
        result = map_relationships("hr_hub", HR_ENTITY_RELS, HR_ENTITY_DEFS)
        rel = _find(result, "employee", "department")
        assert rel is not None
        assert rel.relation_type == "belongs_to"
        assert rel.label == "Employee belongs to Department"

    def test_hr_hub_employee_has_many_leave_requests(self) -> None:
        result = map_relationships("hr_hub", HR_ENTITY_RELS, HR_ENTITY_DEFS)
        rel = _find(result, "employee", "leave_request")
        assert rel is not None
        assert rel.relation_type == "has_many"
        assert rel.label == "Employee has many Leave Requests"

    def test_hr_hub_leave_request_belongs_to_employee(self) -> None:
        result = map_relationships("hr_hub", HR_ENTITY_RELS, HR_ENTITY_DEFS)
        rel = _find(result, "leave_request", "employee")
        assert rel is not None
        assert rel.relation_type == "belongs_to"
        assert rel.label == "Leave Request belongs to Employee"

    def test_hr_hub_no_department_to_leave_request_relationship(self) -> None:
        """department → leave_request must NOT exist (indirect chain, not in YAML)."""
        result = map_relationships("hr_hub", HR_ENTITY_RELS, HR_ENTITY_DEFS)
        assert _find(result, "department", "leave_request") is None

    def test_hr_hub_no_leave_request_to_department_relationship(self) -> None:
        """leave_request → department must NOT exist (indirect chain, not in YAML)."""
        result = map_relationships("hr_hub", HR_ENTITY_RELS, HR_ENTITY_DEFS)
        assert _find(result, "leave_request", "department") is None

    # --- many_to_many support -------------------------------------------

    def test_ticketing_many_to_many_agent_ticket(self) -> None:
        result = map_relationships("ticketing", TICKETING_ENTITY_RELS, TICKETING_ENTITY_DEFS)
        rel = _find(result, "agent", "ticket")
        assert rel is not None
        assert rel.relation_type == "many_to_many"
        assert rel.label == "Agent and Tickets are many-to-many"

    # --- label override from YAML ---------------------------------------

    def test_yaml_label_overrides_auto_generated_label(self) -> None:
        custom_rels = [_rel("employee", "department", "belongs_to", label="Staff is in Dept")]
        result = map_relationships("hr_hub", custom_rels, HR_ENTITY_DEFS)
        assert result[0].label == "Staff is in Dept"

    def test_yaml_label_none_triggers_auto_generation(self) -> None:
        rels = [_rel("employee", "department", "belongs_to", label=None)]
        result = map_relationships("hr_hub", rels, HR_ENTITY_DEFS)
        assert result[0].label == "Employee belongs to Department"

    # --- label fallback when entity_defs is empty -----------------------

    def test_auto_label_falls_back_when_entity_defs_empty(self) -> None:
        rels = [_rel("leave_request", "employee", "belongs_to")]
        result = map_relationships("hr_hub", rels, {})
        assert result[0].label == "Leave Request belongs to Employee"

    # --- bundle_key does not affect output ------------------------------

    def test_bundle_key_does_not_affect_output(self) -> None:
        result_a = map_relationships("hr_hub", HR_ENTITY_RELS, HR_ENTITY_DEFS)
        result_b = map_relationships("generic", HR_ENTITY_RELS, HR_ENTITY_DEFS)
        pairs_a = [(r.source_entity, r.target_entity, r.relation_type) for r in result_a]
        pairs_b = [(r.source_entity, r.target_entity, r.relation_type) for r in result_b]
        assert pairs_a == pairs_b


# ---------------------------------------------------------------------------
# Private helper
# ---------------------------------------------------------------------------


def _find(
    relationships: list[EntityRelationship],
    source: str,
    target: str,
) -> EntityRelationship | None:
    return next(
        (r for r in relationships if r.source_entity == source and r.target_entity == target),
        None,
    )