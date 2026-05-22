"""Unit tests for preview_generator/nodes/emit.py — build_manifest and emit_preview."""

from __future__ import annotations

from agents.preview_generator.nodes.emit import build_manifest, emit_preview
from agents.preview_generator.schemas import KpiMetric, UserContext
from agents.preview_generator.state import PreviewGeneratorState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(**overrides) -> PreviewGeneratorState:
    defaults = dict(
        session_id="sess-test",
        bundle_key="hr_management",
        user_context=UserContext(company_name="Acme Corp", company_size="mid-sized"),
        feature_flags={"hrhub-module": True, "dashboard-module": True},
        sample_tickets=[{"id": 1, "name": "Support Queue"}],
        sample_projects=[{"id": 1, "name": "Alpha Project"}],
        sample_employees=[
            {
                "id": 1,
                "position": "Director",
                "team": "Ops",
                "department": "Operations",
                "job_title": "Director",
                "job_type": "Full-Time",
                "job_level": "Director",
            }
        ],
        kpi_metrics=[
            KpiMetric(
                key="attendance_rate",
                label="Attendance Rate",
                type="percentage",
                source_service="hr_hub",
                sample_value=95.0,
            )
        ],
    )
    defaults.update(overrides)
    return PreviewGeneratorState(**defaults)


# ---------------------------------------------------------------------------
# build_manifest — shape and required sections
# ---------------------------------------------------------------------------


def test_build_manifest_schema_version() -> None:
    manifest = build_manifest(_make_state())
    assert manifest["schema_version"] == "2.0"


def test_build_manifest_has_required_sections() -> None:
    manifest = build_manifest(_make_state())
    for section in ("tenant", "tickets", "projects", "dashboard", "kpi", "hr_hub"):
        assert section in manifest, f"missing section: {section}"


# ---------------------------------------------------------------------------
# build_manifest — tenant field sourcing
# ---------------------------------------------------------------------------


def test_build_manifest_tenant_from_user_context() -> None:
    state = _make_state(
        user_context=UserContext(company_name="Globex", company_size="enterprise")
    )
    manifest = build_manifest(state)
    assert manifest["tenant"]["company_name"] == "Globex"
    assert manifest["tenant"]["size_band"] == "enterprise"


def test_build_manifest_tenant_defaults_when_no_context() -> None:
    state = _make_state(user_context=None)
    manifest = build_manifest(state)
    assert manifest["tenant"]["company_name"] == "Generated Tenant"
    assert manifest["tenant"]["size_band"] == "unknown"


# ---------------------------------------------------------------------------
# build_manifest — KPI ID assignment
# ---------------------------------------------------------------------------


def test_build_manifest_kpi_ids_are_sequential() -> None:
    kpis = [
        KpiMetric(key=f"kpi_{i}", label=f"KPI {i}", type="count", source_service="hr_hub", sample_value=i)
        for i in range(3)
    ]
    manifest = build_manifest(_make_state(kpi_metrics=kpis))
    ids = [k["id"] for k in manifest["kpi"]["kpis"]]
    assert ids == [1, 2, 3]


# ---------------------------------------------------------------------------
# emit_preview — output shape
# ---------------------------------------------------------------------------


def test_emit_preview_output_shape() -> None:
    result = emit_preview(_make_state())
    assert "output" in result
    output = result["output"]
    assert isinstance(output["modules"], list)
    assert isinstance(output["manifest"], dict)
    assert output["manifest"]["schema_version"] == "2.0"
