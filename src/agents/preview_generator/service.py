"""Service wrapper around the compiled preview generator LangGraph pipeline."""

from __future__ import annotations

from catalog.bundle_catalog import BundleCatalog
from core.exceptions import PreviewGenerationError
from core.logging import get_logger, get_session_logger
from domain.models.extraction_result import ExtractionResult

from .pipeline import compiled_graph, compiled_graph_skip_sample_data
from .schemas import UserContext
from .state import PreviewGeneratorState

logger = get_logger(__name__)


class PreviewGeneratorService:
    """Thin wrapper around the compiled LangGraph pipeline.

    API surface is intentionally narrow — callers pass the three required inputs
    plus two optional context fields and receive the two output dicts directly.

    No TemplateRepository dependency. All data is generated programmatically
    inside the pipeline nodes.
    """

    def __init__(self, catalog: BundleCatalog, *, build_manifest: bool = False) -> None:
        self._catalog = catalog
        self._build_manifest = build_manifest

    def generate(
        self,
        session_id: str,
        bundle_key: str,
        conversation_history: list[dict],
        extraction_result: ExtractionResult | None = None,
        preselected_intent: str | None = None,
    ) -> tuple[list[str], UserContext | None]:
        """Run preview pipeline and return v2-facing fields only.

        Returns (modules, user_context).
        """
        session_logger = get_session_logger(__name__, session_id)
        session_logger.info("Starting v2 preview generation for bundle=%s", bundle_key)

        initial_state = PreviewGeneratorState(
            session_id=session_id,
            bundle_key=bundle_key,
            conversation_history=conversation_history,
            extraction_result=extraction_result,
            preselected_intent=preselected_intent,
            catalog=self._catalog,
        )
        graph = (
            compiled_graph_skip_sample_data if self._build_manifest else compiled_graph
        )
        result: dict = graph.invoke(initial_state)

        raw = result.get("output")
        if not isinstance(raw, dict):
            raise PreviewGenerationError(
                f"Pipeline produced no output for bundle={bundle_key}"
            )
        modules = raw.get("modules", [])
        user_context: UserContext | None = result.get("user_context")
        session_logger.info(
            "v2 preview generation complete for bundle=%s modules=%s",
            bundle_key,
            modules,
        )
        return (modules if isinstance(modules, list) else [], user_context)
