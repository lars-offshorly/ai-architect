"""Service wrapper around the compiled preview generator LangGraph pipeline."""

from __future__ import annotations

from core.exceptions import PreviewGenerationError
from core.logging import get_logger, get_session_logger
from domain.models.extraction_result import ExtractionResult

from .pipeline import compiled_graph
from .schemas import PreviewOutput
from .state import PreviewGeneratorState

logger = get_logger(__name__)


class PreviewGeneratorService:
    """Thin wrapper around the compiled LangGraph pipeline.

    API surface is intentionally narrow — callers pass the three required inputs
    plus two optional context fields and receive the two output dicts directly.

    No TemplateRepository dependency. All data is generated programmatically
    inside the pipeline nodes.
    """

    def generate(
        self,
        session_id: str,
        bundle_key: str,
        conversation_history: list[dict],
        extraction_result: ExtractionResult | None = None,
        preselected_intent: str | None = None,
    ) -> tuple[dict, dict]:
        """Run the preview pipeline and return (generation_json, dummy_data_json).

        Args:
            session_id:           Session identifier (passed through to state/logs).
            bundle_key:           Selected bundle (e.g. "project_mgmt", "hr_hub").
            conversation_history: Raw messages from ConversationRepository,
                                  each a dict with "role" and "content" keys.
            extraction_result:    Dev A's accumulated ExtractionResult, if available.
                                  When present, extract_user_context maps its fields
                                  directly — no redundant LLM call is made.
            preselected_intent:   User-chosen intent before conversation (e.g.
                                  "onboarding"). Supplements workflow hints when
                                  classification_signals is empty.

        Returns:
            generation_json  — Knit workspace config (feature_flags, modules, config).
            dummy_data_json  — Sample data stores (employees, projects, tickets, …).
        """
        session_logger = get_session_logger(__name__, session_id)
        session_logger.info("Starting preview generation for bundle=%s", bundle_key)

        initial_state = PreviewGeneratorState(
            session_id=session_id,
            bundle_key=bundle_key,
            conversation_history=conversation_history,
            extraction_result=extraction_result,
            preselected_intent=preselected_intent,
        )

        result: dict = compiled_graph.invoke(initial_state)

        raw = result.get("output")
        if raw is None:
            raise PreviewGenerationError(
                f"Pipeline produced no output for bundle={bundle_key}"
            )
        output = PreviewOutput.model_validate(raw) if isinstance(raw, dict) else raw

        session_logger.info(
            "Preview generation complete for bundle=%s modules=%s",
            bundle_key,
            output.generation_json.modules,
        )
        return output.generation_json.model_dump(), output.dummy_data_json.model_dump()
