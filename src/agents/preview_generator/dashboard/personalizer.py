"""Dashboard template personalizer.

Applies user-context signals from the conversation to a deep-copied dashboard
template before it is sent to the dashboard generation service.

Personalization strategy:
1. ``dashboard_name`` — inject company name, remove "Template" suffix.
2. ``report`` — LLM-generated summary using conversation context; falls back
   to keyword-based substitution when LLM is unavailable or fails.
3. Date ranges on ``data_config`` widgets — set sensible defaults when
   ``date_from`` / ``date_to`` are null (last 12 months from today).
4. Department ``fields`` on chart widgets — replace with teams from
   ``UserContext`` when available.
"""

from __future__ import annotations

import copy
import re
from datetime import date, timedelta

from langchain_core.messages import HumanMessage, SystemMessage

from agents.preview_generator.schemas import UserContext
from core.config import get_settings
from core.llm import get_openai_chat_model
from core.logging import get_logger

from .prompts import DASHBOARD_REPORT_SYSTEM_PROMPT

logger = get_logger(__name__)

# Placeholder used in template dashboard_name / report fields.
_COMPANY_PLACEHOLDER_RE = re.compile(r"\bTemplate\b", re.IGNORECASE)

# Number of recent user messages included in the LLM context window.
_HISTORY_WINDOW = 5


def personalize_template(
    template: dict,
    user_context: UserContext | None,
    bundle_key: str,
    conversation_history: list[dict] | None = None,
) -> dict:
    """Return a personalized copy of ``template`` for the given session context.

    Mutations applied (all are no-ops when the relevant signal is absent):
    1. ``dashboard_name`` — inject company name, remove "Template" suffix.
    2. ``report`` — LLM-generated summary when API key is configured; keyword
       substitution otherwise.
    3. Date ranges on ``data_config`` widgets — set sensible defaults when
       ``date_from`` / ``date_to`` are null (last 12 months from today).
    4. Department ``fields`` on chart widgets — replace with teams from
       ``UserContext`` when available.

    Args:
        template:             Raw template dict (deep-copied before mutation).
        user_context:         Pipeline-produced context; may be None for Tier 3
                              or very short conversations.
        bundle_key:           Registry/catalog key (used for log context).
        conversation_history: Raw conversation turns for LLM report generation;
                              falls back to keyword replacement when absent.

    Returns:
        A personalized copy of the template dict, ready to POST.
    """
    payload = copy.deepcopy(template)

    company_name = (
        user_context.company_name
        if user_context and user_context.company_name
        else None
    )
    team_names = (
        [t.name for t in user_context.teams if t.name]
        if user_context and user_context.teams
        else []
    )

    _personalize_dashboard_name(payload, company_name)
    _personalize_report(payload, user_context, bundle_key, conversation_history or [])
    _personalize_widgets(payload, team_names)

    logger.info(
        "Personalized dashboard template for bundle=%s company=%s teams=%d",
        bundle_key,
        company_name or "(none)",
        len(team_names),
    )
    return payload


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _personalize_dashboard_name(payload: dict, company_name: str | None) -> None:
    name: str = payload.get("dashboard_name", "")
    if company_name:
        name = _COMPANY_PLACEHOLDER_RE.sub(company_name, name)
        if "Template" not in name and company_name not in name:
            name = f"{name} — {company_name}"
    payload["dashboard_name"] = name


def _personalize_report(
    payload: dict,
    user_context: UserContext | None,
    bundle_key: str,
    conversation_history: list[dict],
) -> None:
    """Write the report field: LLM-generated if possible, keyword fallback otherwise."""
    existing_report: str = payload.get("report", "")
    if not isinstance(existing_report, str):
        return

    company_name = (
        user_context.company_name
        if user_context and user_context.company_name
        else None
    )

    # Skip personalization entirely if there's no context to personalize with.
    if not company_name and not conversation_history:
        return

    # Attempt LLM generation first.
    llm_report = _generate_report_via_llm(
        user_context, bundle_key, conversation_history, existing_report
    )
    if llm_report:
        payload["report"] = llm_report
        logger.debug("Dashboard report personalised via LLM for bundle=%s", bundle_key)
        return

    # Keyword fallback: replace "Template" occurrences with the company name.
    if company_name:
        payload["report"] = _COMPANY_PLACEHOLDER_RE.sub(company_name, existing_report)


def _build_llm_human_message(
    user_context: UserContext | None,
    bundle_key: str,
    conversation_history: list[dict],
    fallback_report: str,
) -> str:
    """Build the human-turn message sent to the LLM for report generation."""
    parts: list[str] = []

    company = user_context.company_name if user_context else None
    industry = user_context.industry_detail if user_context else None
    concern = user_context.primary_concern if user_context else None
    teams = (
        [t.name for t in user_context.teams if t.name]
        if user_context and user_context.teams
        else []
    )

    if company:
        parts.append(f"Company: {company}")
    if industry:
        parts.append(f"Industry: {industry}")
    if teams:
        parts.append(f"Teams: {', '.join(teams)}")
    if concern:
        parts.append(f"Primary concern: {concern}")

    parts.append(f"Bundle: {bundle_key.replace('_', ' ').title()}")

    user_msgs = [
        m["content"]
        for m in conversation_history
        if m.get("role") == "user" and m.get("content")
    ][-_HISTORY_WINDOW:]
    if user_msgs:
        parts.append("Conversation excerpt:\n" + "\n".join(user_msgs))

    parts.append(f"Existing report text (improve / replace):\n{fallback_report}")
    return "\n\n".join(parts)


def _generate_report_via_llm(
    user_context: UserContext | None,
    bundle_key: str,
    conversation_history: list[dict],
    fallback_report: str,
) -> str | None:
    """Call the LLM to generate a personalised report string.

    Returns the generated text on success, or None on any failure (no API key,
    network error, empty response). The caller applies the keyword fallback.
    """
    settings = get_settings()
    if not settings.OPENAI_API_KEY:
        return None

    human_message = _build_llm_human_message(
        user_context, bundle_key, conversation_history, fallback_report
    )

    try:
        llm = get_openai_chat_model(temperature=settings.ASSEMBLER_TEMPERATURE)
        response = llm.invoke(
            [
                SystemMessage(content=DASHBOARD_REPORT_SYSTEM_PROMPT),
                HumanMessage(content=human_message),
            ]
        )
        text: str = response.content.strip() if response and response.content else ""
        return text if text else None
    except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        logger.warning(
            "LLM report generation failed for bundle=%s: %s", bundle_key, exc
        )
        return None


def _personalize_widgets(payload: dict, team_names: list[str]) -> None:
    today = date.today()
    default_date_from = (today - timedelta(days=365)).isoformat()
    default_date_to = today.isoformat()

    for widget in payload.get("widgets", []):
        data_config = widget.get("data_config")
        if not isinstance(data_config, dict):
            continue

        # Fill null date ranges with the last 12 months.
        if data_config.get("date_from") is None:
            data_config["date_from"] = default_date_from
        if data_config.get("date_to") is None:
            data_config["date_to"] = default_date_to

        # Replace empty/generic department fields with team names from context.
        if team_names and isinstance(data_config.get("fields"), list):
            existing_fields = data_config["fields"]
            if not existing_fields:
                data_config["fields"] = team_names[:6]  # cap to keep payload sane
