"""Orchestrator: runs preview pipeline and assembles v2 AppPayload."""

from __future__ import annotations

import re
from typing import Any

from agents.tenant_provisioning.service import TenantProvisioningService
from core.exceptions import PreviewGenerationError
from core.logging import get_logger, get_session_logger
from domain.models.app_payload import AppPayload
from domain.models.extraction_result import ExtractionResult

logger = get_logger(__name__)


# Region/locale/timezone defaults inferred from common location keywords. Keep
# this list short and explicit; deeper geo-IP-style resolution belongs in a
# proper service, not regex.
_REGION_KEYWORDS: dict[str, dict[str, str]] = {
    "PH": {
        "primary_region": "APAC",
        "locale": "en-PH",
        "timezone": "Asia/Manila",
        "keywords": "philippines from ph manila cebu davao",
    },
    "US": {
        "primary_region": "NA",
        "locale": "en-US",
        "timezone": "America/New_York",
        "keywords": "united states usa american",
    },
    "UK": {
        "primary_region": "EMEA",
        "locale": "en-GB",
        "timezone": "Europe/London",
        "keywords": "united kingdom britain england london",
    },
}


def _size_band_for_count(count: int) -> str:
    if count <= 10:
        return "1-10"
    if count <= 50:
        return "11-50"
    if count <= 200:
        return "51-200"
    if count <= 500:
        return "200-500"
    if count <= 1000:
        return "500-1000"
    return "1000+"


def _derive_tenant_overrides(
    extraction_result: ExtractionResult | None,
    conversation_history: list[dict],
) -> dict[str, str]:
    """Build per-call tenant overrides from extraction + raw history.

    Reads company name from extraction signals first, then falls back to a
    deterministic regex over the conversation. Size band and region are
    inferred from raw message content.
    """
    overrides: dict[str, str] = {}

    # 1. Company name: prefer extractor's structured signal.
    company_name = ""
    if extraction_result is not None:
        company_name = extraction_result.personalization_signals.company_name or ""
    full_text = "\n".join(str(msg.get("content", "")) for msg in conversation_history)
    if not company_name:
        company_name = _extract_company_name_from_text(full_text)
    if company_name:
        overrides["company_name"] = company_name

    # 2. Team size → size band.
    size_match = re.search(
        r"\b(\d{1,4})\s+(?:people|person|users?|employees?|team)\b",
        full_text,
        flags=re.IGNORECASE,
    )
    if size_match:
        overrides["size_band"] = _size_band_for_count(int(size_match.group(1)))

    # 3. Region / locale / timezone.
    lowered = full_text.lower()
    for spec in _REGION_KEYWORDS.values():
        keywords = spec["keywords"].split()
        if any(re.search(rf"\b{re.escape(kw)}\b", lowered) for kw in keywords):
            overrides["primary_region"] = spec["primary_region"]
            overrides["locale"] = spec["locale"]
            overrides["timezone"] = spec["timezone"]
            break

    return overrides


_COMPANY_NAME_PATTERN = re.compile(
    (
        r"\b(?:"
        r"company\s+(?:called|named|name(?:'?s|d)?)"
        r"|business\s+(?:called|named)"
        r"|team\s+(?:called|named)"
        r"|(?:we|i)['’]?re?\s+called"
        r"|called"
        r"|named"
        r"|name\s+is"
        r"|by\s+the\s+name\s+of"
        r")\s+"
        r"([A-Z0-9][A-Za-z0-9 '&.\-]{0,60}?)"
        r"(?=\s+(?:and|with|that|for|in|is|was|who|which|because|so|to)\b"
        r"|[.,!?;:]|$)"
    ),
    flags=re.IGNORECASE,
)


def _extract_company_name_from_text(text: str) -> str:
    match = _COMPANY_NAME_PATTERN.search(text)
    if not match:
        return ""
    return match.group(1).strip(" .,!?:;'\"")


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

        tenant_overrides = _derive_tenant_overrides(
            extraction_result=extraction_result,
            conversation_history=conversation_history,
        )
        if tenant_overrides:
            session_logger.info(
                "Tenant overrides derived: %s", sorted(tenant_overrides.keys())
            )

        manifest = self._build_manifest(
            session_id=session_id,
            bundle_key=bundle_key,
            conversation_history=conversation_history,
            tenant_overrides=tenant_overrides or None,
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
        tenant_overrides: dict[str, str] | None = None,
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
                tenant_overrides=tenant_overrides,
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
