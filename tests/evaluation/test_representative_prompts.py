"""Representative prompt evaluation tests for AI Bundle Classifier.

Tests cover all AD-4 decision tree branches:
1. High confidence single bundle (proceed)
2. Ambiguous tie-gap scenarios (suggest_alternatives)
3. Missing critical fields (clarify)
4. Clarification budget exhaustion (fallback_generic)
5. Multi-intent detection
6. Unknown domain handling

These tests validate the complete pipeline: extraction → classification → fallback → recommendation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agents.interpreter.classifier import Classifier
from agents.interpreter.extractor import Extractor
from agents.interpreter.fallback import FallbackHandler
from agents.interpreter.signal_accumulator import SignalAccumulator
from catalog.bundle_catalog import BundleCatalog
from domain.models.extraction_result import ExtractionResult
from domain.services.bundle_recommendation import BundleRecommendationService


@pytest.fixture(name="catalog")
def fixture_catalog(shared_catalog: BundleCatalog) -> BundleCatalog:
    """Use the session-scoped bundle catalog for evaluation."""
    return shared_catalog


@pytest.fixture(name="fallback_handler")
def fixture_fallback_handler(catalog: BundleCatalog) -> FallbackHandler:
    """Create fallback handler with production thresholds."""
    return FallbackHandler(
        catalog=catalog,
        proceed_threshold=0.75,
        suggest_threshold=0.50,
        score_gap_minimum=0.15,
        max_clarification_turns=3,
    )


@pytest.fixture(name="recommendation_service")
def fixture_recommendation_service(
    catalog: BundleCatalog,
) -> BundleRecommendationService:
    """Create recommendation service."""
    return BundleRecommendationService(catalog=catalog)


# =============================================================================
# Test Category 1: High Confidence - Proceed Path
# =============================================================================


@pytest.mark.asyncio
async def test_clear_hr_intent_proceeds(
    catalog: BundleCatalog,
    fallback_handler: FallbackHandler,
    recommendation_service: BundleRecommendationService,
) -> None:
    """Clear HR-specific request should proceed with high confidence."""
    prompt = (
        "I need to track employee leave requests, manage attendance, "
        "and handle onboarding for new hires. We have about 50 employees."
    )

    # Extract signals
    extraction = ExtractionResult(
        session_id="test-hr",
        classification_signals={
            "keywords": ["track", "leave", "attendance", "onboarding"],
            "entities": ["employee", "leave request"],
            "intents": ["manage employees", "track attendance", "onboard new hires"],
            "workflow_hints": ["hr workflow"],
            "domain_hints": ["human resources"],
            "metrics": ["employee count"],
        },
        personalization_signals={"company_name": None},
        missing_fields=[],
    )

    # Mock classify result with high confidence
    from domain.models.bundle import BundleSuggestion
    from domain.models.classification_result import ClassificationResult

    classification = ClassificationResult(
        session_id="test-hr",
        ranked_candidates=[
            BundleSuggestion(
                bundle_key="hr_management",
                display_name="HR Management",
                confidence=0.85,
                reasoning="Strong HR signals",
                matched_signals=["employee", "leave", "attendance", "onboarding"],
            ),
        ],
    )

    # Apply fallback logic
    result = fallback_handler.apply(classification, extraction, clarification_turn_count=0)

    # Assertions
    assert result.confidence_status == "proceed"
    assert result.selected_bundle is not None
    assert result.selected_bundle.bundle_key == "hr_management"
    assert result.top_confidence >= 0.75
    assert result.score_gap >= 0.15

    # Test recommendation
    recommendation = recommendation_service.recommend(result, extraction)
    assert recommendation.recommendation_status == "ready"
    assert recommendation.primary_bundle is not None
    assert recommendation.primary_bundle.bundle_key == "hr_management"


@pytest.mark.asyncio
async def test_clear_ticketing_intent_proceeds(
    catalog: BundleCatalog,
    fallback_handler: FallbackHandler,
) -> None:
    """Clear ticketing/support request should proceed."""
    prompt = (
        "We need a helpdesk system to manage customer support tickets with SLA tracking "
        "and priority queues."
    )

    extraction = ExtractionResult(
        session_id="test-ticket",
        classification_signals={
            "keywords": ["helpdesk", "support", "tickets", "SLA", "queue"],
            "entities": ["ticket", "customer"],
            "intents": ["manage tickets", "track SLA"],
            "workflow_hints": ["support workflow"],
            "domain_hints": ["customer support"],
            "metrics": ["SLA"],
        },
        personalization_signals={},
        missing_fields=[],
    )

    from domain.models.bundle import BundleSuggestion
    from domain.models.classification_result import ClassificationResult

    classification = ClassificationResult(
        session_id="test-ticket",
        ranked_candidates=[
            BundleSuggestion(
                bundle_key="ticketing",
                display_name="Ticketing Tool",
                confidence=0.88,
                reasoning="Strong ticketing signals",
                matched_signals=["ticket", "support", "SLA", "queue"],
            ),
        ],
    )

    result = fallback_handler.apply(classification, extraction, clarification_turn_count=0)

    assert result.confidence_status == "proceed"
    assert result.selected_bundle.bundle_key == "ticketing"


# =============================================================================
# Test Category 2: Ambiguous / Tie-Gap - Suggest Alternatives Path
# =============================================================================


@pytest.mark.asyncio
async def test_ambiguous_sales_vs_marketing(
    catalog: BundleCatalog,
    fallback_handler: FallbackHandler,
) -> None:
    """Ambiguous request that could be sales or marketing."""
    prompt = "I want to track campaigns and leads for my business."

    extraction = ExtractionResult(
        session_id="test-ambiguous",
        classification_signals={
            "keywords": ["track", "campaigns", "leads"],
            "entities": ["campaign", "lead"],
            "intents": ["track campaigns", "manage leads"],
            "workflow_hints": [],
            "domain_hints": [],
            "metrics": [],
        },
        personalization_signals={},
        missing_fields=[],
    )

    from domain.models.bundle import BundleSuggestion
    from domain.models.classification_result import ClassificationResult

    # Close confidence scores - small gap
    classification = ClassificationResult(
        session_id="test-ambiguous",
        ranked_candidates=[
            BundleSuggestion(
                bundle_key="marketing",
                display_name="Marketing",
                confidence=0.62,
                reasoning="Campaign tracking",
                matched_signals=["campaign"],
            ),
            BundleSuggestion(
                bundle_key="sales",
                display_name="Sales",
                confidence=0.58,
                reasoning="Lead management",
                matched_signals=["lead"],
            ),
        ],
    )

    result = fallback_handler.apply(classification, extraction, clarification_turn_count=0)

    # Should suggest alternatives due to small gap (0.04 < 0.15)
    assert result.confidence_status == "suggest_alternatives"
    assert result.selected_bundle.bundle_key == "marketing"
    assert len(result.ranked_candidates) == 2
    assert result.score_gap < 0.15


@pytest.mark.asyncio
async def test_project_vs_construction_ambiguity(
    catalog: BundleCatalog,
    fallback_handler: FallbackHandler,
    recommendation_service: BundleRecommendationService,
) -> None:
    """Project management vs construction - similar workflows."""
    prompt = "I need to manage projects and track milestones for site work."

    extraction = ExtractionResult(
        session_id="test-project-ambiguous",
        classification_signals={
            "keywords": ["projects", "milestones", "site"],
            "entities": ["project", "milestone", "site"],
            "intents": ["manage projects", "track milestones"],
            "workflow_hints": ["project workflow"],
            "domain_hints": [],
            "metrics": [],
        },
        personalization_signals={},
        missing_fields=[],
    )

    from domain.models.bundle import BundleSuggestion
    from domain.models.classification_result import ClassificationResult

    classification = ClassificationResult(
        session_id="test-project-ambiguous",
        ranked_candidates=[
            BundleSuggestion(
                bundle_key="project_mgmt",
                display_name="Project Management",
                confidence=0.65,
                reasoning="Project workflow",
                matched_signals=["project", "milestone"],
            ),
            BundleSuggestion(
                bundle_key="construction",
                display_name="Construction",
                confidence=0.60,
                reasoning="Site work",
                matched_signals=["site"],
            ),
        ],
    )

    result = fallback_handler.apply(classification, extraction, clarification_turn_count=0)

    assert result.confidence_status == "suggest_alternatives"

    # Test recommendation preserves fallbacks
    recommendation = recommendation_service.recommend(result, extraction)
    assert recommendation.recommendation_status == "needs_clarification"
    assert len(recommendation.fallback_bundles) > 0


# =============================================================================
# Test Category 3: Missing Critical Fields - Clarify Path
# =============================================================================


@pytest.mark.asyncio
async def test_missing_company_name_triggers_clarification(
    catalog: BundleCatalog,
    fallback_handler: FallbackHandler,
) -> None:
    """Request with low confidence and missing critical field."""
    prompt = "I want to manage employees and their leave."

    from domain.enums.missing_field_type import MissingFieldType

    extraction = ExtractionResult(
        session_id="test-missing",
        classification_signals={
            "keywords": ["manage", "employees", "leave"],
            "entities": ["employee", "leave"],
            "intents": ["manage employees"],
            "workflow_hints": [],
            "domain_hints": [],
            "metrics": [],
        },
        personalization_signals={},
        missing_fields=[MissingFieldType.COMPANY_NAME],  # Critical field missing
    )

    from domain.models.bundle import BundleSuggestion
    from domain.models.classification_result import ClassificationResult

    classification = ClassificationResult(
        session_id="test-missing",
        ranked_candidates=[
            BundleSuggestion(
                bundle_key="hr_management",
                display_name="HR Management",
                confidence=0.40,  # Below suggest_threshold so critical missing check applies
                reasoning="Employee management",
                matched_signals=["employee", "leave"],
            ),
        ],
    )

    result = fallback_handler.apply(classification, extraction, clarification_turn_count=0)

    # Should clarify due to critical missing field
    assert result.confidence_status == "clarify"
    assert MissingFieldType.COMPANY_NAME.value in result.missing_context


@pytest.mark.asyncio
async def test_vague_request_triggers_clarification(
    catalog: BundleCatalog,
    fallback_handler: FallbackHandler,
) -> None:
    """Very vague request with low confidence."""
    prompt = "I need to track some stuff for my business."

    extraction = ExtractionResult(
        session_id="test-vague",
        classification_signals={
            "keywords": ["track", "stuff", "business"],
            "entities": [],
            "intents": [],
            "workflow_hints": [],
            "domain_hints": [],
            "metrics": [],
        },
        personalization_signals={},
        missing_fields=[],
    )

    from domain.models.bundle import BundleSuggestion
    from domain.models.classification_result import ClassificationResult

    classification = ClassificationResult(
        session_id="test-vague",
        ranked_candidates=[
            BundleSuggestion(
                bundle_key="generic",
                display_name="Custom Workspace",
                confidence=0.25,
                reasoning="Insufficient information",
                matched_signals=[],
            ),
        ],
    )

    result = fallback_handler.apply(classification, extraction, clarification_turn_count=0)

    assert result.confidence_status == "clarify"
    assert result.top_confidence < 0.50


# =============================================================================
# Test Category 4: Clarification Budget Exhaustion - Fallback Generic
# =============================================================================


@pytest.mark.asyncio
async def test_clarification_budget_exhausted_falls_back(
    catalog: BundleCatalog,
    fallback_handler: FallbackHandler,
    recommendation_service: BundleRecommendationService,
) -> None:
    """After max clarification turns, system falls back to generic."""
    prompt = "I still don't know, just something generic."

    extraction = ExtractionResult(
        session_id="test-exhausted",
        classification_signals={
            "keywords": ["generic", "something"],
            "entities": [],
            "intents": [],
            "workflow_hints": [],
            "domain_hints": [],
            "metrics": [],
        },
        personalization_signals={},
        missing_fields=[],
    )

    from domain.models.bundle import BundleSuggestion
    from domain.models.classification_result import ClassificationResult

    classification = ClassificationResult(
        session_id="test-exhausted",
        ranked_candidates=[
            BundleSuggestion(
                bundle_key="hr_management",
                display_name="HR Management",
                confidence=0.30,
                reasoning="Weak signals",
                matched_signals=[],
            ),
        ],
    )

    # Simulate 3 clarification turns already happened
    result = fallback_handler.apply(
        classification, extraction, clarification_turn_count=3  # Max reached
    )

    # Should fall back to generic
    assert result.confidence_status == "fallback_generic"
    assert result.selected_bundle.bundle_key == "generic"
    assert "exhausted" in result.reasoning.lower() or "fallback" in result.reasoning.lower()

    # Test recommendation
    recommendation = recommendation_service.recommend(result, extraction)
    assert recommendation.recommendation_status == "fallback_generic"
    assert recommendation.primary_bundle.bundle_key == "generic"


@pytest.mark.asyncio
async def test_repeated_ambiguous_requests_exhaust_budget(
    catalog: BundleCatalog,
    fallback_handler: FallbackHandler,
) -> None:
    """Multiple ambiguous responses eventually trigger generic fallback."""
    extraction = ExtractionResult(
        session_id="test-repeated",
        classification_signals={
            "keywords": ["maybe", "not sure"],
            "entities": [],
            "intents": [],
            "workflow_hints": [],
            "domain_hints": [],
            "metrics": [],
        },
        personalization_signals={},
        missing_fields=[],
    )

    from domain.models.bundle import BundleSuggestion
    from domain.models.classification_result import ClassificationResult

    classification = ClassificationResult(
        session_id="test-repeated",
        ranked_candidates=[
            BundleSuggestion(
                bundle_key="project_mgmt",
                display_name="Project Management",
                confidence=0.40,
                reasoning="Uncertain",
                matched_signals=[],
            ),
        ],
    )

    # Turn 1-2: should still clarify
    result_turn1 = fallback_handler.apply(classification, extraction, clarification_turn_count=1)
    assert result_turn1.confidence_status == "clarify"

    result_turn2 = fallback_handler.apply(classification, extraction, clarification_turn_count=2)
    assert result_turn2.confidence_status == "clarify"

    # Turn 3: budget exhausted, fallback
    result_turn3 = fallback_handler.apply(classification, extraction, clarification_turn_count=3)
    assert result_turn3.confidence_status == "fallback_generic"


# =============================================================================
# Test Category 5: Multi-Intent Detection
# =============================================================================


@pytest.mark.asyncio
async def test_multi_intent_hr_and_projects(
    catalog: BundleCatalog,
    fallback_handler: FallbackHandler,
) -> None:
    """User wants both HR and project management features."""
    prompt = (
        "I need to manage both employees with leave tracking and also handle "
        "projects with task assignments."
    )

    extraction = ExtractionResult(
        session_id="test-multi",
        classification_signals={
            "keywords": ["employees", "leave", "projects", "tasks"],
            "entities": ["employee", "leave", "project", "task"],
            "intents": ["manage employees", "track leave", "manage projects"],
            "workflow_hints": ["hr workflow", "project workflow"],
            "domain_hints": [],
            "metrics": [],
        },
        personalization_signals={},
        missing_fields=[],
    )

    from domain.models.bundle import BundleSuggestion
    from domain.models.classification_result import ClassificationResult

    # Both bundles have reasonable confidence
    classification = ClassificationResult(
        session_id="test-multi",
        ranked_candidates=[
            BundleSuggestion(
                bundle_key="hr_management",
                display_name="HR Management",
                confidence=0.68,
                reasoning="Employee management",
                matched_signals=["employee", "leave"],
            ),
            BundleSuggestion(
                bundle_key="project_mgmt",
                display_name="Project Management",
                confidence=0.65,
                reasoning="Project workflow",
                matched_signals=["project", "task"],
            ),
        ],
    )

    result = fallback_handler.apply(classification, extraction, clarification_turn_count=0)

    # Should suggest alternatives for multi-intent
    assert result.confidence_status == "suggest_alternatives"
    assert len(result.ranked_candidates) >= 2


# =============================================================================
# Test Category 6: Unknown Domain Handling
# =============================================================================


@pytest.mark.asyncio
async def test_unknown_domain_triggers_clarification(
    catalog: BundleCatalog,
    fallback_handler: FallbackHandler,
) -> None:
    """Completely unknown business domain."""
    prompt = "I run a pet grooming business and need to track appointments."

    extraction = ExtractionResult(
        session_id="test-unknown",
        classification_signals={
            "keywords": ["pet", "grooming", "appointments"],
            "entities": ["appointment"],
            "intents": ["track appointments"],
            "workflow_hints": [],
            "domain_hints": ["pet grooming"],  # Not a supported domain
            "metrics": [],
        },
        personalization_signals={},
        missing_fields=[],
    )

    from domain.models.bundle import BundleSuggestion
    from domain.models.classification_result import ClassificationResult

    # System might map to healthcare or ticketing but with low confidence
    classification = ClassificationResult(
        session_id="test-unknown",
        ranked_candidates=[
            BundleSuggestion(
                bundle_key="ticketing",
                display_name="Ticketing Tool",
                confidence=0.45,
                reasoning="Appointment tracking",
                matched_signals=["appointment"],
            ),
        ],
    )

    result = fallback_handler.apply(classification, extraction, clarification_turn_count=0)

    # Should clarify for unknown domain
    assert result.confidence_status == "clarify"
    assert result.top_confidence < 0.50


@pytest.mark.asyncio
async def test_niche_industry_with_clear_workflow(
    catalog: BundleCatalog,
    fallback_handler: FallbackHandler,
) -> None:
    """Niche industry but workflow maps clearly to a bundle."""
    prompt = "We're a law firm and need to manage legal cases, client files, and billing."

    extraction = ExtractionResult(
        session_id="test-legal",
        classification_signals={
            "keywords": ["law", "cases", "client", "files", "billing"],
            "entities": ["case", "client"],
            "intents": ["manage cases", "track billing"],
            "workflow_hints": ["legal workflow"],
            "domain_hints": ["legal services"],
            "metrics": [],
        },
        personalization_signals={},
        missing_fields=[],
    )

    from domain.models.bundle import BundleSuggestion
    from domain.models.classification_result import ClassificationResult

    classification = ClassificationResult(
        session_id="test-legal",
        ranked_candidates=[
            BundleSuggestion(
                bundle_key="legal_services",
                display_name="Legal Services",
                confidence=0.82,
                reasoning="Legal case management",
                matched_signals=["case", "legal", "client"],
            ),
        ],
    )

    result = fallback_handler.apply(classification, extraction, clarification_turn_count=0)

    # Should proceed - legal is a supported bundle
    assert result.confidence_status == "proceed"
    assert result.selected_bundle.bundle_key == "legal_services"


# =============================================================================
# Test Category 7: Score Gap Edge Cases
# =============================================================================


@pytest.mark.asyncio
async def test_exact_score_gap_threshold(
    catalog: BundleCatalog,
    fallback_handler: FallbackHandler,
) -> None:
    """Test behavior when score gap exactly equals threshold."""
    extraction = ExtractionResult(
        session_id="test-gap-edge",
        classification_signals={
            "keywords": ["finance", "budget"],
            "entities": ["budget"],
            "intents": ["track budget"],
            "workflow_hints": [],
            "domain_hints": [],
            "metrics": [],
        },
        personalization_signals={},
        missing_fields=[],
    )

    from domain.models.bundle import BundleSuggestion
    from domain.models.classification_result import ClassificationResult

    # Gap exactly 0.15 (threshold)
    classification = ClassificationResult(
        session_id="test-gap-edge",
        ranked_candidates=[
            BundleSuggestion(
                bundle_key="finance",
                display_name="Finance",
                confidence=0.75,  # Exactly at proceed threshold
                reasoning="Budget tracking",
                matched_signals=["budget"],
            ),
            BundleSuggestion(
                bundle_key="project_mgmt",
                display_name="Project Management",
                confidence=0.60,  # Gap = 0.15
                reasoning="Budget planning",
                matched_signals=[],
            ),
        ],
    )

    result = fallback_handler.apply(classification, extraction, clarification_turn_count=0)

    # Should proceed when gap >= threshold and confidence >= threshold
    assert result.confidence_status == "proceed"
    assert result.score_gap >= 0.15


@pytest.mark.asyncio
async def test_high_confidence_small_gap_suggests_alternatives(
    catalog: BundleCatalog,
    fallback_handler: FallbackHandler,
) -> None:
    """High confidence but small gap should suggest alternatives."""
    extraction = ExtractionResult(
        session_id="test-high-conf-small-gap",
        classification_signals={
            "keywords": ["healthcare", "patients"],
            "entities": ["patient"],
            "intents": ["manage patients"],
            "workflow_hints": [],
            "domain_hints": [],
            "metrics": [],
        },
        personalization_signals={},
        missing_fields=[],
    )

    from domain.models.bundle import BundleSuggestion
    from domain.models.classification_result import ClassificationResult

    classification = ClassificationResult(
        session_id="test-high-conf-small-gap",
        ranked_candidates=[
            BundleSuggestion(
                bundle_key="healthcare",
                display_name="Healthcare",
                confidence=0.78,  # Above proceed threshold
                reasoning="Patient management",
                matched_signals=["patient"],
            ),
            BundleSuggestion(
                bundle_key="ticketing",
                display_name="Ticketing Tool",
                confidence=0.72,  # Small gap of 0.06
                reasoning="Patient tickets",
                matched_signals=[],
            ),
        ],
    )

    result = fallback_handler.apply(classification, extraction, clarification_turn_count=0)

    # Should suggest alternatives because gap < 0.15 despite high confidence
    assert result.confidence_status == "suggest_alternatives"
    assert result.score_gap < 0.15


# =============================================================================
# Test Category 8: Preselected Bundle Path
# =============================================================================


@pytest.mark.asyncio
async def test_preselected_bundle_bypasses_classification(
    catalog: BundleCatalog,
    recommendation_service: BundleRecommendationService,
) -> None:
    """When user pre-selects bundle, recommendation uses it directly."""
    extraction = ExtractionResult(
        session_id="test-preselected",
        classification_signals={
            "keywords": ["employees"],
            "entities": ["employee"],
            "intents": [],
            "workflow_hints": [],
            "domain_hints": [],
            "metrics": [],
        },
        personalization_signals={},
        missing_fields=[],
    )

    from domain.models.bundle import BundleSuggestion
    from domain.models.classification_result import ClassificationResult

    # Classification still runs but bundle is preselected
    classification = ClassificationResult(
        session_id="test-preselected",
        selected_bundle=BundleSuggestion(
            bundle_key="hr_management",
            display_name="HR Management",
            confidence=1.0,
            reasoning="Preselected by user",
            matched_signals=[],
        ),
        ranked_candidates=[],
        confidence_status="proceed",
    )

    recommendation = recommendation_service.recommend(
        classification, extraction, preselected_bundle_key="hr_management"
    )

    assert recommendation.recommendation_status == "preselected"
    assert recommendation.primary_bundle.bundle_key == "hr_management"
    assert "pre-selected" in recommendation.reasoning.lower()
