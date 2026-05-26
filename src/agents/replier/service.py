from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from agents.interpreter.provisioning_readiness import ProvisioningReadinessResult
from core.config import get_settings
from core.logging import get_logger, get_session_logger
from domain.enums.missing_field_type import MissingFieldType
from domain.models.bundle import BundleSuggestion
from domain.models.conversation import ConversationMessage
from domain.models.extraction_result import ExtractionResult

from .clarification import (
    generate_clarification_question,
    is_critical,
    known_facts_from_readiness,
    question_for_tenant_field,
)
from .prompts import BUNDLE_SUGGESTION_SYSTEM_PROMPT, BUNDLE_VERIFICATION_SYSTEM_PROMPT

logger = get_logger(__name__)


class ReplierService:
    def __init__(self) -> None:
        settings = get_settings()
        self._model = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            temperature=settings.CONVERSATIONAL_TEMPERATURE,
            api_key=settings.OPENAI_API_KEY,
        )

    async def build_clarification(
        self,
        session_id: str,
        extracted: ExtractionResult,
        bundle_key: str,
        history: list[ConversationMessage] | None = None,
        readiness: ProvisioningReadinessResult | None = None,
    ) -> tuple[MissingFieldType | None, str]:
        session_logger = get_session_logger(__name__, session_id)
        missing = extracted.missing_fields

        critical = [f for f in missing if is_critical(f)]
        target = critical[0] if critical else (missing[0] if missing else None)

        if target is None:
            # No ``MissingFieldType`` left to ask about — but the
            # readiness gate may still flag tenant fields (industry,
            # company name, size band, region). Surface a deterministic
            # question for the first missing required tenant field so the
            # flow doesn't return an empty awaiting_input.
            if readiness is not None and readiness.missing_required:
                next_field = readiness.missing_required[0]
                session_logger.info(
                    "No MissingFieldType; asking about tenant field=%s",
                    next_field.value,
                )
                return None, question_for_tenant_field(next_field)
            session_logger.info("No missing fields detected")
            return None, ""

        slots = extracted.to_extracted_info().slots
        known_facts = (
            known_facts_from_readiness(readiness, slots)
            if readiness is not None
            else None
        )
        question = await generate_clarification_question(
            self._model,
            target,
            bundle_key,
            slots,
            variants=None,
            history=history,
            readiness=readiness,
            known_facts=known_facts,
        )
        session_logger.info("Clarification needed for field=%s", target.value)
        return target, question

    async def build_bundle_verification_question(
        self,
        session_id: str,
        display_name: str,
        slots: dict[str, object],
        history: list[ConversationMessage] | None = None,
        readiness: ProvisioningReadinessResult | None = None,
    ) -> str:
        session_logger = get_session_logger(__name__, session_id)
        context = self._build_verification_context(
            display_name=display_name,
            slots=slots,
            history=history,
            readiness=readiness,
        )
        try:
            response = await self._model.ainvoke(
                [
                    SystemMessage(content=BUNDLE_VERIFICATION_SYSTEM_PROMPT),
                    HumanMessage(content=context),
                ]
            )
            question = str(response.content).strip()
        except (RuntimeError, ValueError, TypeError) as exc:
            session_logger.error(
                "Bundle verification question generation failed: %s", exc
            )
            question = (
                "Could you tell me a bit more about your team — "
                "like how many people are involved and how you currently manage things?"
            )
        return question

    @staticmethod
    def _build_verification_context(
        display_name: str,
        slots: dict[str, object],
        history: list[ConversationMessage] | None,
        readiness: ProvisioningReadinessResult | None,
    ) -> str:
        sections: list[str] = []
        recent = (history or [])[-6:]
        if recent:
            history_text = "\n".join(f"{m.role}: {m.content}" for m in recent)
            sections.append(f"Recent conversation:\n{history_text}")

        sections.append(f"Workspace category: {display_name}")

        if readiness is not None:
            known_facts = known_facts_from_readiness(readiness, slots)
            if known_facts:
                lines = [f"- {k}: {v}" for k, v in known_facts.items() if v]
                if lines:
                    sections.append("Known tenant facts:\n" + "\n".join(lines))
            missing_required = [f.value for f in readiness.missing_required]
            missing_optional = [f.value for f in readiness.missing_optional]
            if missing_required:
                sections.append(
                    "Ask about (required, in order): " + ", ".join(missing_required)
                )
            elif missing_optional:
                sections.append(
                    "Ask about (optional, in order): " + ", ".join(missing_optional)
                )
            else:
                sections.append("All tenant facts known — return an empty string.")
        else:
            sections.append(f"Context gathered so far: {slots}")

        return "\n\n".join(sections)

    async def build_bundle_suggestion(
        self,
        session_id: str,
        suggestion: BundleSuggestion,
        slots: dict[str, object],
    ) -> str:
        session_logger = get_session_logger(__name__, session_id)
        try:
            response = await self._model.ainvoke(
                [
                    SystemMessage(content=BUNDLE_SUGGESTION_SYSTEM_PROMPT),
                    HumanMessage(
                        content=(
                            "Recommended workspace: "
                            f"{suggestion.display_name} ({suggestion.bundle_key})\n"
                            f"Workspace category: {suggestion.display_name}\n"
                            f"What we know about the user: {slots}"
                        )
                    ),
                ]
            )
            message = str(response.content).strip()
        except (RuntimeError, ValueError, TypeError) as exc:
            session_logger.error("Bundle suggestion generation failed: %s", exc)
            message = f"I recommend {suggestion.display_name}. Does this look right?"

        return message
