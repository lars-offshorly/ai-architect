"""Integration tests: AI Bundle Classifier output → Preview Generator.

Covers two scenarios Dev A drives:

Scenario A — Classifier output feeds preview (all bundles)
  Simulates what Dev A's classifier produces after a conversation:
  ExtractionResult + SuggestedBundles stored on session.
  Verifies the preview generator uses those signals correctly —
  no redundant extraction, company/dept signals flow through.

Scenario B — "Generate Now" / early preview button
  The user clicks "generate now" mid-conversation before confirming a bundle.
  Three sub-cases:
    B1. preselected_bundle_key passed at session start (Lars scenario #1)
    B2. Classifier has a high-confidence suggestion → early preview uses it
    B3. No bundle at all → fallback to all_microservices with warning
  Each case verifies /preview/early returns 200 + correct bundle_key + warning.

No mocking of the preview pipeline — real stack end to end.
"""

# pylint: disable=missing-class-docstring,missing-function-docstring

from __future__ import annotations

import importlib
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from api.deps import get_conversation_repository, get_session_repository
from domain.models.conversation import ConversationMessage
from domain.models.extraction_result import ExtractionResult, ClassificationSignals, PersonalizationSignals
from domain.models.session import Session


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(name="app", scope="module")
def fixture_app():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
    os.environ["DEBUG"] = "True"
    config_module = importlib.import_module("core.config")
    config_module.get_settings.cache_clear()
    main_module = importlib.import_module("main")
    return main_module.create_app()


@pytest.fixture(name="client")
async def fixture_client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _uid() -> str:
    return str(uuid.uuid4())


_DEFAULT_HISTORY: list[tuple[str, str]] = [
    ("user", "We need a workspace for our team."),
    ("assistant", "Got it. Let me set that up."),
]


def _seed_confirmed(
    bundle_key: str,
    extraction: ExtractionResult | None = None,
    history: list[tuple[str, str]] | None = None,
    latest_classification: dict | None = None,
) -> str:
    """Seed a confirmed session as Dev A would produce after a full conversation.

    Always includes at least one conversation message — the preview endpoint
    requires history to exist.
    """
    sid = _uid()
    session_repo = get_session_repository()
    conv_repo = get_conversation_repository()

    session = Session(
        session_id=sid,
        confirmed=True,
        selected_bundle_key=bundle_key,
        accumulated_extraction=extraction,
        latest_classification=latest_classification,
    )
    session_repo.save(session)

    for role, content in (history if history is not None else _DEFAULT_HISTORY):
        conv_repo.append_message(
            sid, ConversationMessage(role=role, content=content)  # type: ignore[arg-type]
        )
    return sid


def _seed_unconfirmed(
    selected_bundle_key: str | None = None,
    latest_classification: dict | None = None,
    extraction: ExtractionResult | None = None,
    history: list[tuple[str, str]] | None = None,
) -> str:
    """Seed an unconfirmed session (mid-conversation / early preview state).

    Always includes at least one conversation message — the preview endpoint
    requires history to exist.
    """
    sid = _uid()
    session_repo = get_session_repository()
    conv_repo = get_conversation_repository()

    session = Session(
        session_id=sid,
        confirmed=False,
        selected_bundle_key=selected_bundle_key,
        accumulated_extraction=extraction,
        latest_classification=latest_classification,
    )
    session_repo.save(session)

    for role, content in (history if history is not None else _DEFAULT_HISTORY):
        conv_repo.append_message(
            sid, ConversationMessage(role=role, content=content)  # type: ignore[arg-type]
        )
    return sid


def _make_extraction(
    company: str | None = None,
    departments: list[str] | None = None,
    employees: list[str] | None = None,
    roles: list[str] | None = None,
    domain_hints: list[str] | None = None,
    workflow_hints: list[str] | None = None,
    metrics: list[str] | None = None,
    session_id: str = "test",
) -> ExtractionResult:
    """Build a realistic ExtractionResult the way Dev A's extractor would produce it."""
    return ExtractionResult(
        session_id=session_id,
        personalization_signals=PersonalizationSignals(
            company_name=company,
            department_names=departments or [],
            employee_names=employees or [],
            role_names=roles or [],
        ),
        classification_signals=ClassificationSignals(
            domain_hints=domain_hints or [],
            workflow_hints=workflow_hints or [],
            metrics=metrics or [],
        ),
    )


# ===========================================================================
# Scenario A — Classifier extraction signals flow into preview
# ===========================================================================


class TestClassifierToPreviewHRManagement:
    """Dev A classified hr_management with a rich ExtractionResult."""

    @pytest.mark.asyncio
    async def test_company_name_from_extraction_result(
        self, client: AsyncClient
    ) -> None:
        extraction = _make_extraction(
            company="Vertex Solutions",
            departments=["Onboarding", "Compliance"],
            employees=["Maria Santos", "Carlos Mendez"],
            roles=["HR Manager", "Compliance Officer"],
            domain_hints=["hr", "human resources"],
            workflow_hints=["leave management", "onboarding"],
        )
        sid = _seed_confirmed("hr_management", extraction=extraction)

        data = (await client.post(f"/sessions/{sid}/preview")).json()
        assert data["dummy_data_json"]["company_name"] == "Vertex Solutions"

    @pytest.mark.asyncio
    async def test_hr_flags_enabled(self, client: AsyncClient) -> None:
        extraction = _make_extraction(company="Vertex Solutions")
        sid = _seed_confirmed("hr_management", extraction=extraction)

        data = (await client.post(f"/sessions/{sid}/preview")).json()
        flag_map = {f["name"]: f["isEnabled"] for f in data["generation_json"]["feature_flags"]}
        assert flag_map.get("hrhub-module") is True

    @pytest.mark.asyncio
    async def test_hr_stores_populated(self, client: AsyncClient) -> None:
        extraction = _make_extraction(company="Vertex Solutions")
        sid = _seed_confirmed("hr_management", extraction=extraction)

        data = (await client.post(f"/sessions/{sid}/preview")).json()
        stores = data["dummy_data_json"]["stores"]
        assert "tickets" in stores and len(stores["tickets"]) > 0
        assert "queues" in stores and len(stores["queues"]) > 0
        assert "kpis" in stores and len(stores["kpis"]) > 0

    @pytest.mark.asyncio
    async def test_hr_default_kpis_present(self, client: AsyncClient) -> None:
        extraction = _make_extraction(company="Vertex Solutions")
        sid = _seed_confirmed("hr_management", extraction=extraction)

        data = (await client.post(f"/sessions/{sid}/preview")).json()
        kpi_keys = {k["key"] for k in data["dummy_data_json"]["stores"]["kpis"]}
        assert "active_headcount" in kpi_keys

    @pytest.mark.asyncio
    async def test_metric_signal_boosts_kpi(self, client: AsyncClient) -> None:
        """When Dev A's classifier signals a metric, it should be boosted into KPIs."""
        extraction = _make_extraction(
            company="Vertex Solutions",
            metrics=["attendance_rate"],
        )
        sid = _seed_confirmed("hr_management", extraction=extraction)

        data = (await client.post(f"/sessions/{sid}/preview")).json()
        kpi_keys = {k["key"] for k in data["dummy_data_json"]["stores"]["kpis"]}
        assert "attendance_rate" in kpi_keys

    @pytest.mark.asyncio
    async def test_extraction_result_no_redundant_keyword_scan(
        self, client: AsyncClient
    ) -> None:
        """When ExtractionResult is present the pipeline must use it directly.
        Verify by passing history with no company mention — company still appears
        because it came from ExtractionResult, not the keyword scan.
        """
        extraction = _make_extraction(company="SilentCorp")
        # History with no company mention — keyword scan alone would find nothing
        sid = _seed_confirmed(
            "hr_management",
            extraction=extraction,
            history=[("user", "We need an HR workspace."), ("assistant", "Sure.")],
        )
        data = (await client.post(f"/sessions/{sid}/preview")).json()
        assert data["dummy_data_json"]["company_name"] == "SilentCorp"


class TestClassifierToPreviewProjectMgmt:
    """Dev A classified project_mgmt."""

    @pytest.mark.asyncio
    async def test_project_stores_present(self, client: AsyncClient) -> None:
        extraction = _make_extraction(
            company="NovaBuild",
            departments=["Engineering", "QA"],
            workflow_hints=["sprints", "milestones"],
        )
        sid = _seed_confirmed("project_mgmt", extraction=extraction)

        data = (await client.post(f"/sessions/{sid}/preview")).json()
        stores = data["dummy_data_json"]["stores"]
        assert "tasks" in stores
        assert "milestones" in stores

    @pytest.mark.asyncio
    async def test_project_company_from_extraction(self, client: AsyncClient) -> None:
        extraction = _make_extraction(company="NovaBuild")
        sid = _seed_confirmed("project_mgmt", extraction=extraction)

        data = (await client.post(f"/sessions/{sid}/preview")).json()
        assert data["dummy_data_json"]["company_name"] == "NovaBuild"

    @pytest.mark.asyncio
    async def test_project_kpi_signal_from_classifier(
        self, client: AsyncClient
    ) -> None:
        extraction = _make_extraction(
            company="NovaBuild",
            metrics=["cycle_time"],
        )
        sid = _seed_confirmed("project_mgmt", extraction=extraction)

        data = (await client.post(f"/sessions/{sid}/preview")).json()
        kpi_keys = {k["key"] for k in data["dummy_data_json"]["stores"]["kpis"]}
        assert "cycle_time" in kpi_keys

    @pytest.mark.asyncio
    async def test_projects_flag_enabled(self, client: AsyncClient) -> None:
        extraction = _make_extraction(company="NovaBuild")
        sid = _seed_confirmed("project_mgmt", extraction=extraction)

        data = (await client.post(f"/sessions/{sid}/preview")).json()
        flag_map = {f["name"]: f["isEnabled"] for f in data["generation_json"]["feature_flags"]}
        assert flag_map.get("projects-module") is True


class TestClassifierToPreviewTicketing:
    """Dev A classified ticketing."""

    @pytest.mark.asyncio
    async def test_ticketing_stores_present(self, client: AsyncClient) -> None:
        extraction = _make_extraction(
            company="ClearPath",
            domain_hints=["IT support", "help desk"],
            workflow_hints=["SLA", "ticket resolution"],
        )
        sid = _seed_confirmed("ticketing", extraction=extraction)

        data = (await client.post(f"/sessions/{sid}/preview")).json()
        stores = data["dummy_data_json"]["stores"]
        assert "tickets" in stores
        assert "queues" in stores

    @pytest.mark.asyncio
    async def test_ticketing_company_from_extraction(
        self, client: AsyncClient
    ) -> None:
        extraction = _make_extraction(company="ClearPath")
        sid = _seed_confirmed("ticketing", extraction=extraction)

        data = (await client.post(f"/sessions/{sid}/preview")).json()
        assert data["dummy_data_json"]["company_name"] == "ClearPath"

    @pytest.mark.asyncio
    async def test_sla_kpi_boosted_by_classifier_signal(
        self, client: AsyncClient
    ) -> None:
        extraction = _make_extraction(
            company="ClearPath",
            metrics=["sla_compliance"],
        )
        sid = _seed_confirmed("ticketing", extraction=extraction)

        data = (await client.post(f"/sessions/{sid}/preview")).json()
        kpi_keys = {k["key"] for k in data["dummy_data_json"]["stores"]["kpis"]}
        assert "sla_compliance" in kpi_keys

    @pytest.mark.asyncio
    async def test_ticketing_without_extraction_falls_back_to_keyword_scan(
        self, client: AsyncClient
    ) -> None:
        """No ExtractionResult — pipeline falls back to keyword scan on history."""
        sid = _seed_confirmed(
            "ticketing",
            extraction=None,
            history=[
                ("user", "We handle IT tickets at GridLine Systems. SLA is critical."),
                ("assistant", "Ticketing with SLA tracking confirmed."),
            ],
        )
        data = (await client.post(f"/sessions/{sid}/preview")).json()
        assert data["bundle_key"] == "ticketing"
        assert data["dummy_data_json"]["company_name"] == "GridLine Systems"


class TestClassifierToPreviewTier3:
    """Dev A classified a bundle with no Tier 1 registry entry (Tier 3 fallback)."""

    @pytest.mark.asyncio
    async def test_finance_returns_200(self, client: AsyncClient) -> None:
        extraction = _make_extraction(company="FinCorp")
        sid = _seed_confirmed("finance", extraction=extraction)

        resp = await client.post(f"/sessions/{sid}/preview")
        assert resp.status_code == 200, resp.text

    @pytest.mark.asyncio
    async def test_finance_bundle_key_preserved(self, client: AsyncClient) -> None:
        extraction = _make_extraction(company="FinCorp")
        sid = _seed_confirmed("finance", extraction=extraction)

        data = (await client.post(f"/sessions/{sid}/preview")).json()
        assert data["bundle_key"] == "finance"

    @pytest.mark.asyncio
    async def test_healthcare_returns_200(self, client: AsyncClient) -> None:
        extraction = _make_extraction(company="MediCare Plus")
        sid = _seed_confirmed("healthcare", extraction=extraction)

        resp = await client.post(f"/sessions/{sid}/preview")
        assert resp.status_code == 200, resp.text

    @pytest.mark.asyncio
    async def test_tier3_company_name_from_extraction(
        self, client: AsyncClient
    ) -> None:
        """Even Tier 3 bundles should use the company name from ExtractionResult."""
        extraction = _make_extraction(company="LegalEdge")
        sid = _seed_confirmed("legal_services", extraction=extraction)

        data = (await client.post(f"/sessions/{sid}/preview")).json()
        assert data["dummy_data_json"]["company_name"] == "LegalEdge"

    @pytest.mark.asyncio
    async def test_tier3_all_flags_enabled(self, client: AsyncClient) -> None:
        extraction = _make_extraction(company="SalesCo")
        sid = _seed_confirmed("sales", extraction=extraction)

        data = (await client.post(f"/sessions/{sid}/preview")).json()
        enabled = [f for f in data["generation_json"]["feature_flags"] if f["isEnabled"]]
        assert len(enabled) == 69


# ===========================================================================
# Scenario B — "Generate Now" / Early Preview button
# ===========================================================================


class TestGenerateNowPreselectedBundle:
    """B1 — User (or UI) passes preselected_bundle_key at session start.

    The frontend knows which bundle to show before the classifier runs.
    Session gets selected_bundle_key immediately; /preview/early uses it.
    """

    @pytest.mark.asyncio
    async def test_preselected_hr_early_preview_returns_200(
        self, client: AsyncClient
    ) -> None:
        sid = _seed_unconfirmed(selected_bundle_key="hr_management")
        resp = await client.post(f"/sessions/{sid}/preview/early")
        assert resp.status_code == 200, resp.text

    @pytest.mark.asyncio
    async def test_preselected_bundle_key_in_response(
        self, client: AsyncClient
    ) -> None:
        sid = _seed_unconfirmed(selected_bundle_key="hr_management")
        data = (await client.post(f"/sessions/{sid}/preview/early")).json()
        assert data["bundle_key"] == "hr_management"
        assert data["display_name"] == "HR Management"

    @pytest.mark.asyncio
    async def test_early_preview_always_includes_warning(
        self, client: AsyncClient
    ) -> None:
        """Every early preview must carry a warning — conversation is incomplete."""
        sid = _seed_unconfirmed(selected_bundle_key="project_mgmt")
        data = (await client.post(f"/sessions/{sid}/preview/early")).json()
        assert data["warning"] is not None
        assert len(data["warning"]) > 0

    @pytest.mark.asyncio
    async def test_preselected_project_mgmt_stores_populated(
        self, client: AsyncClient
    ) -> None:
        sid = _seed_unconfirmed(selected_bundle_key="project_mgmt")
        data = (await client.post(f"/sessions/{sid}/preview/early")).json()
        stores = data["dummy_data_json"]["stores"]
        assert "tasks" in stores
        assert "milestones" in stores

    @pytest.mark.asyncio
    async def test_preselected_ticketing_stores_populated(
        self, client: AsyncClient
    ) -> None:
        sid = _seed_unconfirmed(selected_bundle_key="ticketing")
        data = (await client.post(f"/sessions/{sid}/preview/early")).json()
        stores = data["dummy_data_json"]["stores"]
        assert "tickets" in stores
        assert "queues" in stores

    @pytest.mark.asyncio
    async def test_early_preview_schema_fields_complete(
        self, client: AsyncClient
    ) -> None:
        sid = _seed_unconfirmed(selected_bundle_key="hr_management")
        data = (await client.post(f"/sessions/{sid}/preview/early")).json()
        for field in ("schema_version", "session_id", "bundle_key", "display_name",
                      "modules", "generation_json", "dummy_data_json", "warning"):
            assert field in data, f"Missing field: {field}"


class TestGenerateNowFromClassifier:
    """B2 — Classifier produced a high-confidence suggestion mid-conversation.

    No confirmed bundle yet, but latest_classification.top_bundle_key is set.
    /preview/early should use that suggestion.
    """

    @pytest.mark.asyncio
    async def test_uses_classifier_top_bundle_key(
        self, client: AsyncClient
    ) -> None:
        sid = _seed_unconfirmed(
            latest_classification={
                "top_bundle_key": "project_mgmt",
                "confidence_status": "proceed",
                "suggestions": [{"bundle_key": "project_mgmt", "confidence": 0.92}],
            }
        )
        data = (await client.post(f"/sessions/{sid}/preview/early")).json()
        assert data["bundle_key"] == "project_mgmt"

    @pytest.mark.asyncio
    async def test_classifier_hr_bundle_early_preview(
        self, client: AsyncClient
    ) -> None:
        sid = _seed_unconfirmed(
            latest_classification={
                "top_bundle_key": "hr_management",
                "confidence_status": "proceed",
                "suggestions": [{"bundle_key": "hr_management", "confidence": 0.88}],
            }
        )
        data = (await client.post(f"/sessions/{sid}/preview/early")).json()
        assert data["bundle_key"] == "hr_management"
        assert data["display_name"] == "HR Management"

    @pytest.mark.asyncio
    async def test_classifier_result_with_extraction_uses_company(
        self, client: AsyncClient
    ) -> None:
        """ExtractionResult present alongside classifier output — company should flow through."""
        extraction = _make_extraction(company="PeakCorp")
        sid = _seed_unconfirmed(
            latest_classification={
                "top_bundle_key": "ticketing",
                "confidence_status": "proceed",
                "suggestions": [{"bundle_key": "ticketing", "confidence": 0.85}],
            },
            extraction=extraction,
        )
        data = (await client.post(f"/sessions/{sid}/preview/early")).json()
        assert data["bundle_key"] == "ticketing"
        assert data["dummy_data_json"]["company_name"] == "PeakCorp"

    @pytest.mark.asyncio
    async def test_early_preview_carries_warning_even_with_high_confidence(
        self, client: AsyncClient
    ) -> None:
        """Warning is about incomplete conversation, not classifier confidence."""
        sid = _seed_unconfirmed(
            latest_classification={
                "top_bundle_key": "hr_management",
                "confidence_status": "proceed",
                "suggestions": [{"bundle_key": "hr_management", "confidence": 0.99}],
            }
        )
        data = (await client.post(f"/sessions/{sid}/preview/early")).json()
        assert data["warning"] is not None


class TestGenerateNowNoBundle:
    """B3 — User clicks "generate now" with nothing classified yet.

    Falls back to all_microservices with a warning.
    """

    @pytest.mark.asyncio
    async def test_no_bundle_returns_200(self, client: AsyncClient) -> None:
        sid = _seed_unconfirmed()
        resp = await client.post(f"/sessions/{sid}/preview/early")
        assert resp.status_code == 200, resp.text

    @pytest.mark.asyncio
    async def test_no_bundle_falls_back_to_all_microservices(
        self, client: AsyncClient
    ) -> None:
        sid = _seed_unconfirmed()
        data = (await client.post(f"/sessions/{sid}/preview/early")).json()
        assert data["bundle_key"] == "all_microservices"

    @pytest.mark.asyncio
    async def test_no_bundle_warning_present(self, client: AsyncClient) -> None:
        sid = _seed_unconfirmed()
        data = (await client.post(f"/sessions/{sid}/preview/early")).json()
        assert data["warning"] is not None

    @pytest.mark.asyncio
    async def test_no_bundle_extraction_company_still_flows_through(
        self, client: AsyncClient
    ) -> None:
        """Even on all_microservices fallback, company name from extraction appears."""
        extraction = _make_extraction(company="EarlyBird Inc")
        sid = _seed_unconfirmed(extraction=extraction)
        data = (await client.post(f"/sessions/{sid}/preview/early")).json()
        assert data["dummy_data_json"]["company_name"] == "EarlyBird Inc"

    @pytest.mark.asyncio
    async def test_missing_session_returns_404(self, client: AsyncClient) -> None:
        resp = await client.post(f"/sessions/{_uid()}/preview/early")
        assert resp.status_code == 404
