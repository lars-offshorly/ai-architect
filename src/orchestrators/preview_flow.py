"""Orchestrator: runs preview pipeline and assembles v2 AppPayload."""

from __future__ import annotations

from typing import Any

from agents.tenant_provisioning.service import TenantProvisioningService
from core.exceptions import PreviewGenerationError
from core.logging import get_logger, get_session_logger
from domain.models.app_payload import AppPayload
from domain.models.extraction_result import ExtractionResult

logger = get_logger(__name__)


class PreviewFlow:
    """Orchestrates preview generation and assembles v2 AppPayload."""

    def __init__(
        self,
        preview_generator_service: Any,
        bundle_display_names: dict[str, str],
        tenant_provisioning_service: TenantProvisioningService | None = None,
    ) -> None:
        self._preview_gen = preview_generator_service
        self._display_names = bundle_display_names
        self._tenant_provisioning_service = tenant_provisioning_service

    def run(
        self,
        session_id: str,
        bundle_key: str,
        conversation_history: list[dict],
        extraction_result: ExtractionResult | None = None,
        preselected_intent: str | None = None,
        variant_key: str | None = None,
    ) -> AppPayload:
        """Execute the preview pipeline, enrich with dashboard widgets.

        Returns AppPayload.

        Args:
            extraction_result:  Dev A's accumulated ExtractionResult. When present,
                                the pipeline skips its own keyword scan / LLM call.
            preselected_intent: User-chosen intent before conversation started.
            variant_key:        Legacy compatibility input; ignored by canonical
                                runtime path.
        """
        _ = variant_key
        session_logger = get_session_logger(__name__, session_id)
        session_logger.info(
            "Running preview flow for bundle=%s",
            bundle_key,
        )

        modules, _user_context = self._preview_gen.generate(
            session_id=session_id,
            bundle_key=bundle_key,
            conversation_history=conversation_history,
            extraction_result=extraction_result,
            preselected_intent=preselected_intent,
        )

        manifest = self._build_manifest(
            session_id=session_id,
            bundle_key=bundle_key,
            conversation_history=conversation_history,
        )

        if not isinstance(manifest, dict):
            raise PreviewGenerationError(
                f"manifest missing for session={session_id} bundle={bundle_key}"
            )

        payload = AppPayload(
            session_id=session_id,
            bundle_key=bundle_key,
            display_name=self._display_names.get(bundle_key, bundle_key),
            modules=modules,
            manifest=manifest,
        )

        session_logger.info(
            "Preview flow complete for session=%s modules=%s",
            session_id,
            payload.modules,
        )
        return payload

    def _build_manifest(
        self,
        session_id: str,
        bundle_key: str,
        conversation_history: list[dict],
    ) -> dict[str, object] | None:
        """Return manifest from TenantProvisioningService when available."""
        if self._tenant_provisioning_service is None:
            return None
        user_message = _last_user_message(conversation_history)
        try:
            return self._tenant_provisioning_service.provision(
                bundle_key=bundle_key,
                user_message=user_message,
                session_id=session_id,
            )
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning(
                "session=%s — manifest provisioning failed for bundle=%s: %s",
                session_id,
                bundle_key,
                exc,
            )
            return None


def _last_user_message(conversation_history: list[dict]) -> str:
    """Return the content of the last user-role message, or empty string."""
    for msg in reversed(conversation_history):
        if msg.get("role") == "user":
            return str(msg.get("content", ""))
    return ""
