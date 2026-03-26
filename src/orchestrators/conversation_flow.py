from __future__ import annotations

from core.logging import get_logger, get_session_logger
from domain.models.conversation import ConversationMessage

logger = get_logger(__name__)

_FlowResult = dict[str, object]


class ConversationFlow:
    def __init__(
        self,
        interpreter_service: object,
        replier_service: object,
        required_slots_by_bundle: dict[str, list[str]],
    ) -> None:
        self._interpreter = interpreter_service  # type: ignore[assignment]
        self._replier = replier_service  # type: ignore[assignment]
        self._required_slots = required_slots_by_bundle

    async def process_turn(
        self,
        session_id: str,
        user_message: str,
        existing_slots: dict[str, object],
        history: list[ConversationMessage],
        confirmed: bool,
    ) -> _FlowResult:
        session_logger = get_session_logger(__name__, session_id)

        extracted, suggested = await self._interpreter.interpret(
            session_id, user_message, existing_slots, history
        )
        top = self._interpreter.top_bundle(suggested)

        if top is None:
            session_logger.info("No confident bundle — asking clarification")
            _, question = await self._replier.build_clarification(
                session_id, extracted, ["primary_use_case"], "unknown"
            )
            return {
                "status": "awaiting_input",
                "question": question,
                "extracted": extracted,
                "suggested": suggested,
                "slots": extracted.slots,
            }

        required = self._required_slots.get(top.bundle_key, [])
        missing_field, question = await self._replier.build_clarification(
            session_id, extracted, required, top.bundle_key
        )
        if missing_field is not None:
            session_logger.info(
                "Missing field=%s for bundle=%s", missing_field.value, top.bundle_key
            )
            return {
                "status": "awaiting_input",
                "question": question,
                "extracted": extracted,
                "suggested": suggested,
                "slots": extracted.slots,
            }

        if not confirmed:
            message = await self._replier.build_bundle_suggestion(
                session_id, top, extracted.slots
            )
            session_logger.info("Suggesting bundle=%s", top.bundle_key)
            return {
                "status": "pending_confirmation",
                "message": message,
                "bundle_key": top.bundle_key,
                "extracted": extracted,
                "suggested": suggested,
                "slots": extracted.slots,
            }

        session_logger.info("All slots filled and confirmed for bundle=%s", top.bundle_key)
        return {
            "status": "ready_for_preview",
            "bundle_key": top.bundle_key,
            "extracted": extracted,
            "suggested": suggested,
            "slots": extracted.slots,
        }
