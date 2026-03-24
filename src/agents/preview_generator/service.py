from __future__ import annotations

from core.logging import get_logger, get_session_logger

from .pipeline import compiled_graph
from .state import PreviewGeneratorState

logger = get_logger(__name__)


class PreviewGeneratorService:
    """Thin wrapper around the compiled LangGraph pipeline.

    API surface is intentionally narrow — callers pass the three inputs
    that the pipeline needs and receive the two output dicts directly.

    No TemplateRepository dependency. All data is generated programmatically
    inside the pipeline nodes.
    """

    def generate(
        self,
        session_id: str,
        bundle_key: str,
        conversation_history: list[dict],
    ) -> tuple[dict, dict]:
        """Run the preview pipeline and return (generation_json, dummy_data_json).

        Args:
            session_id:           Session identifier (passed through to state/logs).
            bundle_key:           Selected bundle (e.g. "project_mgmt", "hr_hub").
            conversation_history: Raw messages from ConversationRepository,
                                  each a dict with "role" and "content" keys.

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
        )

        result: dict = compiled_graph.invoke(initial_state)

        output: dict = result.get("output") or {}
        generation_json  = output.get("generation_json",  {})
        dummy_data_json  = output.get("dummy_data_json",  {})

        session_logger.info(
            "Preview generation complete for bundle=%s modules=%s",
            bundle_key,
            generation_json.get("modules", []),
        )
        return generation_json, dummy_data_json
