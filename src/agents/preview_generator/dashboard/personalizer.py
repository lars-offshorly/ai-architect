"""Dashboard template personalizer.

Applies user-context signals from the conversation to a deep-copied dashboard
template before it is sent to the dashboard generation service.

No LLM calls — purely deterministic substitution using the ``UserContext``
already produced by the preview pipeline's ``extract_user_context`` node.
"""

from __future__ import annotations

import copy
import re
from datetime import date, timedelta
from typing import Optional

from agents.preview_generator.schemas import UserContext
from core.logging import get_logger

logger = get_logger(__name__)

# Placeholder used in template dashboard_name fields.
_COMPANY_PLACEHOLDER_RE = re.compile(r"\bTemplate\b", re.IGNORECASE)


def personalize_template(
    template: dict,
    user_context: Optional[UserContext],
    bundle_key: str,
) -> dict:
    """Return a personalized copy of ``template`` for the given session context.

    Mutations applied (all are no-ops when the relevant signal is absent):
    1. ``dashboard_name`` — inject company name, remove "Template" suffix.
    2. ``report`` — replace "Template" occurrences with the company name.
    3. Date ranges on ``data_config`` widgets — set sensible defaults when
       ``date_from`` / ``date_to`` are null (last 12 months from today).
    4. Department ``fields`` on chart widgets — replace with teams from
       ``UserContext`` when available.

    Args:
        template:     Deep-copied template dict (mutated in place and returned).
        user_context: Pipeline-produced context; may be None for Tier 3 or
                      very short conversations.
        bundle_key:   Registry/catalog key (used only for log context).

    Returns:
        The mutated template dict, ready to POST.
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
    _personalize_report(payload, company_name)
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


def _personalize_dashboard_name(payload: dict, company_name: Optional[str]) -> None:
    name: str = payload.get("dashboard_name", "")
    if company_name:
        name = _COMPANY_PLACEHOLDER_RE.sub(company_name, name)
        if "Template" not in name and company_name not in name:
            name = f"{name} — {company_name}"
    payload["dashboard_name"] = name


def _personalize_report(payload: dict, company_name: Optional[str]) -> None:
    if not company_name:
        return
    report: str = payload.get("report", "")
    if isinstance(report, str):
        payload["report"] = _COMPANY_PLACEHOLDER_RE.sub(company_name, report)


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
