from __future__ import annotations

import re
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from core.logging import get_logger, get_session_logger
from domain.models.conversation import ConversationMessage

from .prompts import INPUT_SAFETY_CLASSIFIER_SYSTEM_PROMPT

logger = get_logger(__name__)

_IN_SCOPE_WORKSPACE_PATTERNS: tuple[str, ...] = (
    r"\bknit workspace\b",
    r"\bworkspace onboarding\b",
    r"\b(set up|setup|configure|create|build)\b.{0,24}\bworkspace\b",
)

_IN_SCOPE_CORRECTION_PATTERNS: tuple[str, ...] = (
    r"\b(change|switch|update)\b.{0,20}\b(to|as)\b",
    r"\bmy industry is\b",
    r"\bi am\b.{0,20}\b(bpo|construction|hr|recruitment|staffing)\b",
)

_OUTSIDE_SCOPE_SOFTWARE_PATTERNS: tuple[str, ...] = (
    (
        r"\b(code|develop|program|implement)\b.{0,36}\b("
        r"website|web ?app|software|script|backend|frontend)\b"
    ),
    r"\b(write|generate)\b.{0,36}\b(code|source code)\b",
)
_OUTSIDE_SCOPE_UNSUPPORTED_ACTION_PATTERNS: tuple[str, ...] = (
    r"\b(book|reserve|schedule)\b.{0,36}\b(flight|hotel|meeting|appointment)\b",
    r"\b(send|email|message|call|text)\b.{0,36}\b(customer|client|vendor|supplier)\b",
    r"\b(process|pay|charge|refund|transfer)\b.{0,36}\b(payment|invoice|money|funds)\b",
    r"\b(login|sign in|access)\b.{0,36}\b(account|portal|bank|gmail|slack)\b",
)

SafetyLabel = Literal[
    "allow",
    "block",
    "outside_scope",
    "needs_review",
    "prompt_injection",
    "data_exfiltration",
    "self_harm",
    "violence",
    "illegal",
]


class SafetyDecision(BaseModel):
    label: SafetyLabel
    safe_reply: str = ""


class _SafetyOutput(BaseModel):
    label: SafetyLabel = Field(...)
    safe_reply: str = Field(...)


class SafetyClassifier:
    def __init__(self, model: ChatOpenAI | None = None) -> None:
        self._model = model

    async def classify(
        self,
        session_id: str,
        user_message: str,
        history: list[ConversationMessage] | None = None,
    ) -> SafetyDecision:
        deterministic = self._deterministic_decision(user_message)
        if deterministic is not None:
            return deterministic
        if self._is_low_risk_follow_up(user_message):
            return SafetyDecision(
                label="allow",
                safe_reply=self._default_reply_for("allow"),
            )

        if self._model is None:
            return self._heuristic_decision(user_message)

        structured = self._model.with_structured_output(
            _SafetyOutput, method="function_calling"
        )
        try:
            result = await structured.ainvoke(
                [
                    SystemMessage(content=INPUT_SAFETY_CLASSIFIER_SYSTEM_PROMPT),
                    HumanMessage(
                        content=self._build_safety_context(
                            user_message=user_message,
                            history=history or [],
                        )
                    ),
                ]
            )
            output = (
                result
                if isinstance(result, _SafetyOutput)
                else _SafetyOutput.model_validate(result)
            )
            decision = SafetyDecision.model_validate(output.model_dump())
        except (RuntimeError, ValueError, TypeError) as exc:
            get_session_logger(__name__, session_id).error(
                "Safety classifier failed: %s", exc
            )
            decision = self._heuristic_decision(user_message)

        if len(decision.safe_reply.strip().split()) < 4:
            decision.safe_reply = self._default_reply_for(decision.label)
        return decision

    def _deterministic_decision(self, text: str) -> SafetyDecision | None:
        lowered = text.lower()
        if any(
            re.search(pattern, lowered) for pattern in _IN_SCOPE_CORRECTION_PATTERNS
        ):
            return SafetyDecision(
                label="allow",
                safe_reply=self._default_reply_for("allow"),
            )
        if any(re.search(pattern, lowered) for pattern in _IN_SCOPE_WORKSPACE_PATTERNS):
            return SafetyDecision(
                label="allow",
                safe_reply=self._default_reply_for("allow"),
            )
        # outside_scope is context-sensitive; prefer LLM decision to avoid
        # false positives on onboarding phrasing.
        if re.search(
            r"(ignore|override).*(system|developer|instruction|policy)", lowered
        ):
            return SafetyDecision(
                label="prompt_injection",
                safe_reply=self._default_reply_for("prompt_injection"),
            )
        if re.search(
            (
                r"(api[_ -]?key|password|secret|token|\.env|environment "
                r"variable|ssh key|private key)"
            ),
            lowered,
        ):
            return SafetyDecision(
                label="data_exfiltration",
                safe_reply=self._default_reply_for("data_exfiltration"),
            )
        if re.search(r"(kill myself|suicide|self harm|hurt myself)", lowered):
            return SafetyDecision(
                label="self_harm",
                safe_reply=self._default_reply_for("self_harm"),
            )
        if re.search(r"\b(bomb|weapon|murder|assault|shoot)\b", lowered):
            return SafetyDecision(
                label="violence",
                safe_reply=self._default_reply_for("violence"),
            )
        if re.search(r"\b(hack|exploit|malware|phishing|steal)\b", lowered):
            return SafetyDecision(
                label="illegal",
                safe_reply=self._default_reply_for("illegal"),
            )
        return None

    def _heuristic_decision(self, text: str) -> SafetyDecision:
        lowered = text.lower()
        if any(re.search(pattern, lowered) for pattern in _IN_SCOPE_WORKSPACE_PATTERNS):
            label: SafetyLabel = "allow"
        elif any(
            re.search(pattern, lowered) for pattern in _OUTSIDE_SCOPE_SOFTWARE_PATTERNS
        ):
            label = "outside_scope"
        elif any(
            re.search(pattern, lowered)
            for pattern in _OUTSIDE_SCOPE_UNSUPPORTED_ACTION_PATTERNS
        ):
            label = "outside_scope"
        elif re.search(
            r"(ignore|override).*(system|developer|instruction|policy)", lowered
        ):
            label = "prompt_injection"
        elif re.search(
            (
                r"(api[_ -]?key|password|secret|token|\.env|environment "
                r"variable|ssh key|private key)"
            ),
            lowered,
        ):
            label = "data_exfiltration"
        elif re.search(r"(kill myself|suicide|self harm|hurt myself)", lowered):
            label = "self_harm"
        elif re.search(r"\b(bomb|weapon|murder|assault|shoot)\b", lowered):
            label = "violence"
        elif re.search(r"\b(hack|exploit|malware|phishing|steal)\b", lowered):
            label = "illegal"
        else:
            label = "allow"
        return SafetyDecision(
            label=label,
            safe_reply=self._default_reply_for(label),
        )

    @staticmethod
    def _build_safety_context(
        user_message: str, history: list[ConversationMessage]
    ) -> str:
        recent = history[-4:]
        lines: list[str] = []
        if recent:
            lines.append("Recent conversation:")
            for msg in recent:
                lines.append(f"{msg.role}: {msg.content}")
            lines.append("")
        lines.append(f"Latest user message:\n{user_message}")
        return "\n".join(lines)

    @staticmethod
    def _is_low_risk_follow_up(text: str) -> bool:
        lowered = text.strip().lower()
        if not lowered:
            return True
        tokens = re.findall(r"[a-z0-9]+", lowered)
        if not tokens:
            return False
        # Typical onboarding follow-ups: company name, short confirmations,
        # size numbers.
        if len(tokens) <= 3 and all(len(tok) <= 24 for tok in tokens):
            if re.search(
                (
                    r"(api[_ -]?key|password|secret|token|\.env|ssh|private key|"
                    r"ignore|override|hack|bomb|suicide)"
                ),
                lowered,
            ):
                return False
            return True
        return False

    @staticmethod
    def _default_reply_for(label: SafetyLabel) -> str:
        replies: dict[SafetyLabel, str] = {
            "allow": "Please continue with your request and I will process it.",
            "block": (
                "I cannot help with that request. I can help with a safe "
                "alternative."
            ),
            "outside_scope": (
                "I can help configure a Knit workspace only. I cannot execute that "
                "action directly. Tell me the workflow to manage: tickets, projects, "
                "HR, or support."
            ),
            "needs_review": (
                "I need one clarification to proceed safely. Please restate "
                "your goal in neutral terms."
            ),
            "prompt_injection": (
                "I will ignore instruction-overrides and continue only with "
                "trusted task scope."
            ),
            "data_exfiltration": (
                "I cannot access or expose secrets, credentials, or private "
                "files outside scope."
            ),
            "self_harm": (
                "I cannot assist with self-harm. If you are in immediate "
                "danger, call local emergency services now."
            ),
            "violence": (
                "I cannot assist with violence. I can help with safe, legal "
                "alternatives."
            ),
            "illegal": (
                "I cannot assist with illegal activity. I can help with legal "
                "alternatives."
            ),
        }
        return replies[label]
