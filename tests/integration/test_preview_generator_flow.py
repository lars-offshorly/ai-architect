"""Integration tests: Dev A → PreviewGeneratorService.

Simulates what happens after Dev A's conversation flow finishes:
  1. InterpreterService selects a bundle_key (catalog key)
  2. Session is confirmed with session.selected_bundle_key set
  3. ConversationRepository.get_messages() is serialised to conversation_history
  4. PreviewFlow calls PreviewGeneratorService.generate(session_id, bundle_key, history)

These tests call PreviewGeneratorService directly — no FastAPI, no database.
Phase 1 pipeline has no LLM calls so no mocking is needed.

Bundle key mapping under test (catalog → registry):
  hr_management → hr_hub        (Tier 1, key translation)
  project_mgmt  → project_mgmt  (Tier 1)
  ticketing     → ticketing     (Tier 1)
  generic       → generic       (Tier 1, fallback bundle)
  unknown_bundle → (none)       (Tier 3 fallback, non-existent key)
"""

# pylint: disable=missing-class-docstring,missing-function-docstring

from __future__ import annotations

from pathlib import Path

import pytest

from agents.preview_generator.service import PreviewGeneratorService
from catalog.bundle_catalog import BundleCatalog

REGISTRY_PATH = (
    Path(__file__).resolve().parents[2] / "src/templates/bundle_registry.yaml"
)

# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------


@pytest.fixture(name="svc")
def fixture_service() -> PreviewGeneratorService:
    catalog = BundleCatalog(REGISTRY_PATH)
    return PreviewGeneratorService(catalog)


# ---------------------------------------------------------------------------
# Realistic conversation histories Dev A would produce
# ---------------------------------------------------------------------------

_HISTORY_HR_HUB: list[dict] = [
    {
        "role": "assistant",
        "content": "Hi! Tell me about your team and what you need help with.",
    },
    {
        "role": "user",
        "content": (
            "I manage HR at Vertex Solutions, a 200-person company."
            " We struggle with employee onboarding, tracking leave"
            " requests, and keeping everyone aligned on company policy."
        ),
    },
    {
        "role": "assistant",
        "content": (
            "Got it — sounds like HR Hub would be a great fit."
            " It covers onboarding tickets, leave queues, and KPI dashboards."
            " How many people are on your HR team directly?"
        ),
    },
    {
        "role": "user",
        "content": (
            "About 12 people."
            " Maria Santos leads onboarding, Carlos Mendez handles compliance."
        ),
    },
    {
        "role": "assistant",
        "content": (
            "Perfect. HR Hub with onboarding, leave, and compliance modules"
            " — does that match what you need?"
        ),
    },
    {"role": "user", "content": "Yes, that's exactly it."},
]

_HISTORY_PROJECT_OPS: list[dict] = [
    {"role": "assistant", "content": "What does your team work on day-to-day?"},
    {
        "role": "user",
        "content": (
            "We're a 30-person engineering team at NovaBuild."
            " We run two-week sprints and track milestones for each product release."
        ),
    },
    {
        "role": "assistant",
        "content": (
            "Project Ops sounds like the right fit — sprint tasks,"
            " milestone tracking, and KPI dashboards. Does that work?"
        ),
    },
    {"role": "user", "content": "Exactly, we also need capacity utilisation metrics."},
    {
        "role": "assistant",
        "content": "Noted — I'll include capacity utilisation. Confirming Project Ops?",
    },
    {"role": "user", "content": "Confirmed."},
]

_HISTORY_FIELD_SERVICE: list[dict] = [
    {"role": "assistant", "content": "Tell me about the work your team handles."},
    {
        "role": "user",
        "content": (
            "We run an IT help desk at ClearPath."
            " We handle bug reports, access requests,"
            " and SLA-bound support tickets across three departments."
        ),
    },
    {
        "role": "assistant",
        "content": (
            "That's a classic service-desk setup."
            " I'd recommend the ticketing module with SLA tracking"
            " and queue management. Sound right?"
        ),
    },
    {"role": "user", "content": "Yes. We also need resolution time metrics."},
]

_HISTORY_UNKNOWN: list[dict] = [
    {"role": "assistant", "content": "What does your organisation manage?"},
    {
        "role": "user",
        "content": (
            "We track physical equipment — laptops, servers, vehicles"
            " — across five office locations."
        ),
    },
    {
        "role": "assistant",
        "content": ("Let me see what I can configure for that use case."),
    },
    {"role": "user", "content": "Great."},
]

_HISTORY_GENERIC: list[dict] = [
    {
        "role": "user",
        "content": "I'm not sure what I need yet. Just show me something general.",
    },
]

_HISTORY_EMPTY: list[dict] = []


# ---------------------------------------------------------------------------
# Helper: assert generation_json contract
# ---------------------------------------------------------------------------


def _assert_generation_json(generation_json: dict, bundle_key: str) -> None:
    assert generation_json["schema_version"] == "1.0"
    assert generation_json["bundle_key"] == bundle_key

    flags = generation_json["feature_flags"]
    assert isinstance(flags, list)
    assert len(flags) > 0
    for flag in flags:
        assert "id" in flag
        assert "name" in flag
        assert "isEnabled" in flag
        assert isinstance(flag["isEnabled"], bool)
        assert "module" in flag

    assert isinstance(generation_json["modules"], list)

    config = generation_json["config"]
    assert "permission_services" in config
    assert "landing_pages" in config


def _assert_dummy_data_json(dummy_data_json: dict, bundle_key: str) -> None:
    assert dummy_data_json["bundle_key"] == bundle_key
    assert "session_id" in dummy_data_json
    assert "stores" in dummy_data_json
    stores = dummy_data_json["stores"]
    assert "kpis" in stores
    assert "dashboard_widgets" in stores
    assert "dashboard_generation_output" in stores


# ===========================================================================
# 1. HR Management — Tier 1, catalog key "hr_management" → registry "hr_hub"
# ===========================================================================


class TestHRHub:
    def test_returns_tuple(self, svc: PreviewGeneratorService) -> None:
        result = svc.generate("sess-hr-1", "hr_management", _HISTORY_HR_HUB)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_generation_json_structure(self, svc: PreviewGeneratorService) -> None:
        gen, _ = svc.generate("sess-hr-2", "hr_management", _HISTORY_HR_HUB)
        _assert_generation_json(gen, "hr_hub")

    def test_hrhub_flags_enabled(self, svc: PreviewGeneratorService) -> None:
        gen, _ = svc.generate("sess-hr-3", "hr_management", _HISTORY_HR_HUB)
        flag_map = {f["name"]: f["isEnabled"] for f in gen["feature_flags"]}
        assert flag_map["hrhub-module"] is True
        assert flag_map["hrhub-overview"] is True
        assert flag_map["dashboard-module"] is True
        assert flag_map["kpi-module"] is True
        assert flag_map["tickets-module"] is True

    def test_modules_include_hrhub(self, svc: PreviewGeneratorService) -> None:
        gen, _ = svc.generate("sess-hr-4", "hr_management", _HISTORY_HR_HUB)
        assert "HRHub" in gen["modules"]
        assert "Dashboard" in gen["modules"]
        assert "KPI" in gen["modules"]

    def test_dummy_data_store_names(self, svc: PreviewGeneratorService) -> None:
        _, dummy = svc.generate("sess-hr-5", "hr_management", _HISTORY_HR_HUB)
        stores = dummy["stores"]
        # hr_hub template: tickets, queues, kpis, dashboard_widgets
        assert "tickets" in stores
        assert "queues" in stores
        assert "kpis" in stores
        assert "dashboard_widgets" in stores
        # Must NOT use generic internal names
        assert "employees" not in stores
        assert "projects" not in stores

    def test_tickets_store_populated(self, svc: PreviewGeneratorService) -> None:
        _, dummy = svc.generate("sess-hr-6", "hr_management", _HISTORY_HR_HUB)
        assert len(dummy["stores"]["tickets"]) > 0

    def test_company_name_extracted(self, svc: PreviewGeneratorService) -> None:
        _, dummy = svc.generate("sess-hr-7", "hr_management", _HISTORY_HR_HUB)
        # "Vertex Solutions" is mentioned in the conversation
        assert dummy["company_name"] == "Vertex Solutions"

    def test_people_names_appear_in_tickets(self, svc: PreviewGeneratorService) -> None:
        _, dummy = svc.generate("sess-hr-8", "hr_management", _HISTORY_HR_HUB)
        ticket_text = str(dummy["stores"]["tickets"])
        # Maria Santos and Carlos Mendez are mentioned in conversation
        assert "Maria" in ticket_text or "Carlos" in ticket_text

    def test_kpis_populated(self, svc: PreviewGeneratorService) -> None:
        _, dummy = svc.generate("sess-hr-9", "hr_management", _HISTORY_HR_HUB)
        assert len(dummy["stores"]["kpis"]) > 0
        kpi = dummy["stores"]["kpis"][0]
        assert "label" in kpi
        assert "sample_value" in kpi


# ===========================================================================
# 2. Project Mgmt — Tier 1, catalog key = registry key
# ===========================================================================


class TestProjectOps:
    def test_generation_json_bundle_key_preserved(
        self, svc: PreviewGeneratorService
    ) -> None:
        gen, _ = svc.generate("sess-po-1", "project_mgmt", _HISTORY_PROJECT_OPS)
        assert gen["bundle_key"] == "project_mgmt"

    def test_projects_module_flag_enabled(self, svc: PreviewGeneratorService) -> None:
        gen, _ = svc.generate("sess-po-2", "project_mgmt", _HISTORY_PROJECT_OPS)
        flag_map = {f["name"]: f["isEnabled"] for f in gen["feature_flags"]}
        assert flag_map["projects-module"] is True
        assert flag_map["dashboard-module"] is True
        assert flag_map["kpi-module"] is True
        assert flag_map["hrhub-module"] is True

    def test_modules_include_projects(self, svc: PreviewGeneratorService) -> None:
        gen, _ = svc.generate("sess-po-3", "project_mgmt", _HISTORY_PROJECT_OPS)
        assert "Projects" in gen["modules"]

    def test_dummy_data_store_names(self, svc: PreviewGeneratorService) -> None:
        _, dummy = svc.generate("sess-po-4", "project_mgmt", _HISTORY_PROJECT_OPS)
        stores = dummy["stores"]
        # project_mgmt template: tasks, milestones, kpis, dashboard_widgets
        assert "tasks" in stores
        assert "milestones" in stores
        assert "kpis" in stores
        assert "dashboard_widgets" in stores
        assert "tickets" not in stores
        assert "employees" not in stores

    def test_tasks_store_populated(self, svc: PreviewGeneratorService) -> None:
        _, dummy = svc.generate("sess-po-5", "project_mgmt", _HISTORY_PROJECT_OPS)
        assert len(dummy["stores"]["tasks"]) > 0

    def test_milestones_populated(self, svc: PreviewGeneratorService) -> None:
        _, dummy = svc.generate("sess-po-6", "project_mgmt", _HISTORY_PROJECT_OPS)
        assert len(dummy["stores"]["milestones"]) > 0

    def test_capacity_utilisation_kpi_included(
        self, svc: PreviewGeneratorService
    ) -> None:
        # "capacity utilisation" mentioned in conversation → should appear in KPIs
        _, dummy = svc.generate("sess-po-7", "project_mgmt", _HISTORY_PROJECT_OPS)
        kpi_labels = [k["key"] for k in dummy["stores"]["kpis"]]
        assert "capacity_utilization" in kpi_labels

    def test_sprint_methodology_in_milestone_names(
        self, svc: PreviewGeneratorService
    ) -> None:
        _, dummy = svc.generate("sess-po-8", "project_mgmt", _HISTORY_PROJECT_OPS)
        milestone_names = [m["name"] for m in dummy["stores"]["milestones"]]
        # sprint mentioned in conversation →
        # project/milestone names use sprint templates
        sprint_milestones = [n for n in milestone_names if "Sprint" in n]
        assert len(sprint_milestones) > 0


# ===========================================================================
# 3. Ticketing — Tier 1, catalog key = registry key
# ===========================================================================


class TestFieldService:
    def test_bundle_key_preserved_in_output(self, svc: PreviewGeneratorService) -> None:
        gen, _ = svc.generate("sess-fs-1", "ticketing", _HISTORY_FIELD_SERVICE)
        assert gen["bundle_key"] == "ticketing"

    def test_tickets_module_flag_enabled(self, svc: PreviewGeneratorService) -> None:
        gen, _ = svc.generate("sess-fs-2", "ticketing", _HISTORY_FIELD_SERVICE)
        flag_map = {f["name"]: f["isEnabled"] for f in gen["feature_flags"]}
        assert flag_map["tickets-module"] is True
        assert flag_map["hrhub-module"] is True
        assert flag_map["projects-module"] is True

    def test_dummy_data_store_names(self, svc: PreviewGeneratorService) -> None:
        _, dummy = svc.generate("sess-fs-3", "ticketing", _HISTORY_FIELD_SERVICE)
        stores = dummy["stores"]
        assert "tickets" in stores
        assert "queues" in stores
        assert "kpis" in stores
        assert "dashboard_widgets" in stores

    def test_sla_kpi_included(self, svc: PreviewGeneratorService) -> None:
        # "SLA" and "resolution time" mentioned in conversation
        _, dummy = svc.generate("sess-fs-4", "ticketing", _HISTORY_FIELD_SERVICE)
        kpi_keys = [k["key"] for k in dummy["stores"]["kpis"]]
        assert "sla_compliance" in kpi_keys or "avg_resolution_time" in kpi_keys


# ===========================================================================
# 4. Unknown Bundle — Tier 3 fallback (no registry entry)
# ===========================================================================


class TestUnknownBundleTier3:
    def test_does_not_raise(self, svc: PreviewGeneratorService) -> None:
        gen, dummy = svc.generate("sess-unk-1", "unknown_bundle", _HISTORY_UNKNOWN)
        assert gen is not None
        assert dummy is not None

    def test_bundle_key_preserved(self, svc: PreviewGeneratorService) -> None:
        gen, _ = svc.generate("sess-unk-2", "unknown_bundle", _HISTORY_UNKNOWN)
        assert gen["bundle_key"] == "unknown_bundle"

    def test_all_flags_enabled(self, svc: PreviewGeneratorService) -> None:
        gen, _ = svc.generate("sess-unk-3", "unknown_bundle", _HISTORY_UNKNOWN)
        enabled = [f for f in gen["feature_flags"] if f["isEnabled"]]
        assert len(enabled) == 69

    def test_all_modules_present(self, svc: PreviewGeneratorService) -> None:
        gen, _ = svc.generate("sess-unk-4", "unknown_bundle", _HISTORY_UNKNOWN)
        assert len(gen["modules"]) == 10

    def test_stores_use_fallback_names(self, svc: PreviewGeneratorService) -> None:
        _, dummy = svc.generate("sess-unk-5", "unknown_bundle", _HISTORY_UNKNOWN)
        stores = dummy["stores"]
        # Tier 3 fallback schema: items, projects, kpis, dashboard_widgets
        assert "items" in stores
        assert "projects" in stores
        assert "kpis" in stores
        assert "dashboard_widgets" in stores

    def test_kpis_still_populated(self, svc: PreviewGeneratorService) -> None:
        # Even Tier 3 should produce some KPI data
        _, dummy = svc.generate("sess-unk-6", "unknown_bundle", _HISTORY_UNKNOWN)
        assert len(dummy["stores"]["kpis"]) > 0


# ===========================================================================
# 5. Generic — Tier 1 fallback bundle (valid catalog entry)
# ===========================================================================


class TestGenericTier1:
    def test_does_not_raise(self, svc: PreviewGeneratorService) -> None:
        gen, dummy = svc.generate("sess-gen-1", "generic", _HISTORY_GENERIC)
        assert gen is not None
        assert dummy is not None

    def test_output_structure_valid(self, svc: PreviewGeneratorService) -> None:
        gen, dummy = svc.generate("sess-gen-2", "generic", _HISTORY_GENERIC)
        _assert_generation_json(gen, "generic")
        _assert_dummy_data_json(dummy, "generic")


# ===========================================================================
# 6. Empty conversation history
# ===========================================================================


class TestEmptyHistory:
    def test_hr_hub_empty_history_does_not_raise(
        self, svc: PreviewGeneratorService
    ) -> None:
        gen, dummy = svc.generate("sess-empty-1", "hr_management", _HISTORY_EMPTY)
        assert gen is not None
        assert dummy is not None

    def test_hr_hub_empty_history_still_produces_flags(
        self, svc: PreviewGeneratorService
    ) -> None:
        gen, _ = svc.generate("sess-empty-2", "hr_management", _HISTORY_EMPTY)
        flag_map = {f["name"]: f["isEnabled"] for f in gen["feature_flags"]}
        assert flag_map["hrhub-module"] is True

    def test_empty_history_no_company_name(self, svc: PreviewGeneratorService) -> None:
        _, dummy = svc.generate("sess-empty-3", "hr_management", _HISTORY_EMPTY)
        assert dummy["company_name"] is None

    def test_project_ops_empty_history_does_not_raise(
        self, svc: PreviewGeneratorService
    ) -> None:
        gen, dummy = svc.generate("sess-empty-4", "project_mgmt", _HISTORY_EMPTY)
        assert gen["bundle_key"] == "project_mgmt"
        assert "tasks" in dummy["stores"]


# ===========================================================================
# 7. Feature flags — structural integrity across all catalog keys
# ===========================================================================


@pytest.mark.parametrize("catalog_key", ["hr_management", "project_mgmt", "ticketing"])
def test_all_flags_have_required_fields(
    svc: PreviewGeneratorService, catalog_key: str
) -> None:
    gen, _ = svc.generate(f"sess-flags-{catalog_key}", catalog_key, [])
    for flag in gen["feature_flags"]:
        assert "id" in flag, f"Missing 'id' in flag: {flag}"
        assert "name" in flag, f"Missing 'name' in flag: {flag}"
        assert "isEnabled" in flag, f"Missing 'isEnabled' in flag: {flag}"
        assert "module" in flag, f"Missing 'module' in flag: {flag}"


@pytest.mark.parametrize("catalog_key", ["hr_management", "project_mgmt", "ticketing"])
def test_tier1_bundles_have_kpis(
    svc: PreviewGeneratorService, catalog_key: str
) -> None:
    _, dummy = svc.generate(f"sess-kpi-{catalog_key}", catalog_key, [])
    assert len(dummy["stores"]["kpis"]) > 0, f"No KPIs for {catalog_key}"


@pytest.mark.parametrize(
    "catalog_key,expected_store",
    [
        ("hr_management", "tickets"),
        ("project_mgmt", "tasks"),
        ("ticketing", "tickets"),
        ("finance", "items"),
    ],
)
def test_primary_store_name_per_bundle(
    svc: PreviewGeneratorService,
    catalog_key: str,
    expected_store: str,
) -> None:
    _, dummy = svc.generate(f"sess-store-{catalog_key}", catalog_key, [])
    assert expected_store in dummy["stores"], (
        f"Expected store '{expected_store}' for bundle '{catalog_key}', "
        f"got: {list(dummy['stores'].keys())}"
    )


@pytest.mark.parametrize(
    "catalog_key,expected_secondary",
    [
        ("hr_management", "queues"),
        ("project_mgmt", "milestones"),
        ("ticketing", "queues"),
    ],
)
def test_secondary_store_name_per_bundle(
    svc: PreviewGeneratorService,
    catalog_key: str,
    expected_secondary: str,
) -> None:
    _, dummy = svc.generate(f"sess-sec-{catalog_key}", catalog_key, [])
    assert expected_secondary in dummy["stores"], (
        f"Expected store '{expected_secondary}' for bundle '{catalog_key}', "
        f"got: {list(dummy['stores'].keys())}"
    )
