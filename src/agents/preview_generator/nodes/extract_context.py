"""Pipeline node: extracts structured user context from raw conversation history."""

from __future__ import annotations

import re

from core.logging import get_logger

from ..schemas import PersonDetail, TeamDetail, UserContext, WorkItemDetail
from ..state import PreviewGeneratorState

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Keyword sets — Phase 1 (deterministic keyword scan)
# Phase 2 replaces _detect_* with a structured LLM call; these become fallback.
# ---------------------------------------------------------------------------

_LEGAL_KEYWORDS = frozenset(
    [
        "litigation",
        "matter",
        "attorney",
        "paralegal",
        "counsel",
        "court",
        "filing",
        "docket",
        "case",
        "law firm",
        "legal",
        "lawsuit",
        "plaintiff",
        "defendant",
        "deposition",
        "arbitration",
        "settlement",
    ]
)
_TECH_KEYWORDS = frozenset(
    [
        "sprint",
        "standup",
        "backlog",
        "scrum",
        "kanban",
        "agile",
        "developer",
        "engineer",
        "software",
        "deploy",
        "release",
        "codebase",
        "repository",
        "pull request",
        "devops",
        "ci/cd",
    ]
)
_CONSULTING_KEYWORDS = frozenset(
    [
        "engagement",
        "consultant",
        "consulting",
        "deliverable",
        "client work",
        "statement of work",
        "sow",
        "retainer",
        "billable",
        "advisory",
    ]
)
_HR_KEYWORDS = frozenset(
    [
        "onboarding",
        "offboarding",
        "employee",
        "headcount",
        "payroll",
        "performance review",
        "hr",
        "human resources",
        "leave",
        "attendance",
        "recruitment",
        "hiring",
        "org chart",
    ]
)
_AGILE_KEYWORDS = frozenset(
    [
        "sprint",
        "sprints",
        "scrum",
        "kanban",
        "agile",
        "backlog",
        "backlogs",
        "standup",
        "standups",
        "velocity",
        "story points",
        "retrospective",
        "epic",
        "epics",
        "iteration",
        "iterations",
    ]
)
_WATERFALL_KEYWORDS = frozenset(
    [
        "milestone",
        "phase",
        "waterfall",
        "gantt",
        "wbs",
        "work breakdown",
        "baseline",
        "deliverable",
        "gate review",
    ]
)
# Superset of _LEGAL_KEYWORDS — adds "discovery" for work-type detection.
# Any term added to _LEGAL_KEYWORDS is automatically covered here.
_LITIGATION_KEYWORDS = _LEGAL_KEYWORDS | frozenset(["discovery"])
_SUPPORT_KEYWORDS = frozenset(
    [
        "support",
        "helpdesk",
        "help desk",
        "ticket",
        "issue",
        "request",
        "incident",
        "sla",
        "escalation",
        "resolution",
        "service desk",
    ]
)
_REMOTE_KEYWORDS = frozenset(
    [
        "remote",
        "distributed",
        "work from home",
        "wfh",
        "hybrid",
        "across time zones",
        "global team",
        "different locations",
    ]
)
_CLIENT_KEYWORDS = frozenset(
    [
        "clients",
        "client",
        "customers",
        "external",
        "client-facing",
        "customer success",
        "account",
    ]
)
_SMALL_KEYWORDS = frozenset(
    [
        "small team",
        "startup",
        "just us",
        "handful",
        "few of us",
        "small company",
        "small business",
        "solopreneur",
    ]
)
_ENTERPRISE_KEYWORDS = frozenset(
    [
        "enterprise",
        "corporation",
        "large company",
        "thousands of employees",
        "global",
        "multinational",
        "conglomerate",
    ]
)

# Patterns for named-entity extraction
_COMPANY_PATTERNS = [
    re.compile(
        r"(?:we are|we're|we're at|i work at|i'm from|"
        r"our company is|company name is|called|named)"
        r"\s+([A-Z][A-Za-z0-9\s&'.-]{1,40}?)"
        r"(?:\s*[,.]|\s+and\s|\s+we\b)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:at|for)\s+([A-Z][a-z0-9\s&'.-]{1,40}?)(?:\s*[,.]|\s+we\b|\s+our\b)",
        re.IGNORECASE,
    ),
]
_NAME_PATTERNS = [
    re.compile(
        r"(?:my name is|i'm|i am)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", re.IGNORECASE
    ),
    re.compile(r"(?:this is|meet)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", re.IGNORECASE),
]
_ROLE_PATTERNS = [
    re.compile(
        r"i(?:'m| am) (?:a |an )?([a-z\s]{3,30}?)(?:\s+at\b|\s+in\b|\s*[,.])",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:our|the)\s+([A-Za-z\s]{3,25}?)\s+(?:is|are)\s+"
        r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
        re.IGNORECASE,
    ),
]
_TEAM_PATTERNS = [
    re.compile(
        r"(\d+)\s+(?:person |people |member )?(?:team|staff|employee)", re.IGNORECASE
    ),
    re.compile(r"(?:our\s+)?([a-z\s]{3,25}?)\s+team", re.IGNORECASE),
    re.compile(r"([a-z\s]{3,25}?)\s+department", re.IGNORECASE),
]
_SIZE_PATTERNS = [
    re.compile(r"(\d+)\s+(?:person|people|employee|member|staff)", re.IGNORECASE),
    re.compile(r"(?:team of|company of|about)\s+(\d+)", re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _any_kw_in(text: str, keywords: frozenset[str]) -> bool:
    """Match any keyword in text.

    Multi-word phrases (e.g. "law firm", "help desk") use substring search.
    Single-word keywords use \\b word-boundary matching to avoid false hits
    (e.g. "case" should not match "caseload").
    """
    for kw in keywords:
        if " " in kw:
            if kw in text:
                return True
        elif re.search(rf"\b{re.escape(kw)}\b", text):
            return True
    return False


def _user_text(conversation_history: list[dict]) -> str:
    """Concatenate only user messages, lower-cased, for keyword scanning."""
    parts = [m["content"] for m in conversation_history if m.get("role") == "user"]
    return " ".join(parts)


def _raw_user_text(conversation_history: list[dict]) -> str:
    """Concatenate user messages preserving case, for regex extraction."""
    return " ".join(
        m["content"] for m in conversation_history if m.get("role") == "user"
    )


def _detect_industry(text: str) -> tuple[str | None, str | None]:
    """Returns (industry_class, industry_detail).
    industry_class maps to broad category; industry_detail is more specific.
    """
    if _any_kw_in(text, _LEGAL_KEYWORDS):
        return "legal", "Law / Litigation"
    if _any_kw_in(text, _HR_KEYWORDS):
        return "hr", "Human Resources"
    if _any_kw_in(text, _CONSULTING_KEYWORDS):
        return "consulting", "Professional Services / Consulting"
    if _any_kw_in(text, _TECH_KEYWORDS):
        return "technology", "Software / Technology"
    if _any_kw_in(text, _SUPPORT_KEYWORDS):
        return "operations", "IT Support / Service Desk"
    return None, None


def _detect_work_types(text: str) -> list[str]:
    """Returns all work types detected in the text (one per matched keyword set).

    A conversation can reference multiple work styles — e.g. a law firm that
    also runs support tickets would produce ["litigation", "support_request"].
    Defaults to ["waterfall"] when nothing is detected.
    """
    types: list[str] = []
    if _any_kw_in(text, _LITIGATION_KEYWORDS):
        types.append("litigation")
    if _any_kw_in(text, _AGILE_KEYWORDS):
        types.append("sprint")
    if _any_kw_in(text, _WATERFALL_KEYWORDS):
        types.append("waterfall")
    if _any_kw_in(text, _SUPPORT_KEYWORDS):
        types.append("support_request")
    return types or ["waterfall"]  # safe default


def _detect_methodology(text: str) -> str | None:
    if _any_kw_in(text, _AGILE_KEYWORDS):
        return "agile"
    if _any_kw_in(text, _WATERFALL_KEYWORDS):
        return "waterfall"
    if re.search(r"\bkanban\b", text):
        return "kanban"
    return None


def _extract_company_name(raw_text: str) -> str | None:
    for pattern in _COMPANY_PATTERNS:
        match = pattern.search(raw_text)
        if match:
            candidate = match.group(1).strip().strip(".,")
            if 2 <= len(candidate.split()) <= 5 and candidate[0].isupper():
                return candidate
    return None


def _extract_people(raw_text: str) -> list[PersonDetail]:
    people: list[PersonDetail] = []
    seen_names: set[str] = set()

    # "my name is X" or "I am X" — mark as user
    for pattern in _NAME_PATTERNS:
        for match in pattern.finditer(raw_text):
            name = match.group(1).strip()
            if name and name not in seen_names:
                seen_names.add(name)
                people.append(PersonDetail(name=name, is_user=True))

    # "our {role} is {Name}" — extract role-person pairs
    role_pattern = _ROLE_PATTERNS[1]
    for match in role_pattern.finditer(raw_text):
        role = match.group(1).strip()
        name = match.group(2).strip()
        if name and name not in seen_names and len(role.split()) <= 4:
            seen_names.add(name)
            people.append(PersonDetail(name=name, role=role, is_user=False))

    return people[:10]  # cap at 10 to avoid noise


def _extract_teams(_raw_text: str, lower_text: str) -> list[TeamDetail]:
    teams: list[TeamDetail] = []
    seen: set[str] = set()

    known_functions = [
        "engineering",
        "marketing",
        "sales",
        "hr",
        "human resources",
        "legal",
        "operations",
        "product",
        "design",
        "finance",
        "it",
        "support",
        "customer success",
        "data",
        "research",
    ]

    for func in known_functions:
        if func in lower_text:
            key = func.title()
            if key not in seen:
                seen.add(key)
                # Try to extract size
                size_match = re.search(rf"(\d+)\s+(?:person\s+)?{func}", lower_text)
                size = int(size_match.group(1)) if size_match else None
                teams.append(
                    TeamDetail(name=f"{key} Team", size=size, function=func.title())
                )

    return teams[:5]


def _detect_company_size(text: str) -> str | None:
    # Numeric signals
    for pattern in _SIZE_PATTERNS:
        match = pattern.search(text)
        if match:
            n = int(match.group(1))
            if n <= 20:
                return "small"
            if n <= 200:
                return "mid-sized"
            return "enterprise"

    # Keyword signals
    if _any_kw_in(text, _ENTERPRISE_KEYWORDS):
        return "enterprise"
    if _any_kw_in(text, _SMALL_KEYWORDS):
        return "small"
    return None


def _extract_key_phrases(text: str) -> list[str]:
    """Pull signal phrases relevant to KPI and metric matching."""
    targets = [
        "on time",
        "deadline",
        "delivery",
        "resolution",
        "sla",
        "capacity",
        "utilization",
        "workload",
        "headcount",
        "attendance",
        "billable",
        "client satisfaction",
        "cycle time",
        "velocity",
        "case load",
        "throughput",
        "escalation",
    ]
    found = []
    for phrase in targets:
        if phrase in text:
            found.append(phrase)
    return found


# ---------------------------------------------------------------------------
# ExtractionResult → UserContext mapping (Tier 1)
# ---------------------------------------------------------------------------

_METHODOLOGY_HINTS = ("agile", "scrum", "kanban", "waterfall", "hybrid")


def _methodology_from_hints(hints: list[str], intent: str | None) -> str | None:
    """Derive work_methodology from workflow_hints or preselected_intent."""
    sources = hints + ([intent] if intent else [])
    for src in sources:
        lower = src.lower()
        for keyword in _METHODOLOGY_HINTS:
            if keyword in lower:
                return keyword
    return None


def _map_extraction_result(
    extraction_result: "ExtractionResult",  # noqa: F821 — forward ref for clarity
    preselected_intent: str | None,
) -> UserContext:
    """Map Dev A's ExtractionResult directly to UserContext (no LLM call).

    Only sets fields that ExtractionResult can provide. Callers should run
    keyword scan afterward to fill any remaining None fields.
    """
    ps = extraction_result.personalization_signals
    cs = extraction_result.classification_signals

    # People: employee names + role names as separate PersonDetail entries
    people: list[PersonDetail] = []
    seen_names: set[str] = set()
    for name in ps.employee_names:
        if name and name not in seen_names:
            seen_names.add(name)
            people.append(PersonDetail(name=name))
    for role in ps.role_names:
        if role:
            people.append(PersonDetail(role=role))

    # Teams: department names → TeamDetail
    teams: list[TeamDetail] = [
        TeamDetail(name=dept, function=dept)
        for dept in ps.department_names
        if dept
    ]

    # Key phrases: interpreter metrics + custom terminology values
    key_phrases: list[str] = list(cs.metrics)
    key_phrases += [v for v in ps.terminology.values() if v]

    # Supplement with preselected_intent if it isn't a methodology keyword
    if preselected_intent:
        intent_lower = preselected_intent.lower()
        is_methodology = any(kw in intent_lower for kw in _METHODOLOGY_HINTS)
        if not is_methodology and preselected_intent not in key_phrases:
            key_phrases.append(preselected_intent)

    return UserContext(
        company_name=ps.company_name or None,
        industry_detail=cs.domain_hints[0] if cs.domain_hints else None,
        people=people,
        teams=teams,
        work_methodology=_methodology_from_hints(cs.workflow_hints, preselected_intent),
        key_phrases=key_phrases,
    )


def _keyword_fill(ctx: UserContext, history: list[dict]) -> UserContext:
    """Run keyword scan and fill any UserContext fields still None.

    Returns a new UserContext with gaps filled; fields already set are preserved.
    """
    if not history:
        return ctx

    lower = _user_text(history)
    raw = _raw_user_text(history)

    company_name = ctx.company_name or _extract_company_name(raw)
    company_size = ctx.company_size or _detect_company_size(lower)
    _, industry_detail = _detect_industry(lower)
    industry_detail = ctx.industry_detail or industry_detail
    people = ctx.people or _extract_people(raw)
    teams = ctx.teams or _extract_teams(raw, lower)
    methodology = ctx.work_methodology or _detect_methodology(lower)

    has_remote = ctx.has_remote_teams
    if has_remote is None:
        has_remote = any(kw in lower for kw in _REMOTE_KEYWORDS) or None

    has_clients = ctx.has_clients
    if has_clients is None:
        has_clients = any(kw in lower for kw in _CLIENT_KEYWORDS) or None

    # Merge key_phrases — preserve existing, add newly detected
    existing = set(ctx.key_phrases)
    extra = [p for p in _extract_key_phrases(lower) if p not in existing]
    key_phrases = ctx.key_phrases + extra

    has_deadlines = any(
        p in lower for p in ["deadline", "due date", "due by", "by friday"]
    )
    if ctx.work_items:
        work_items = ctx.work_items
    else:
        work_types = _detect_work_types(lower)
        work_items = [
            WorkItemDetail(
                work_type=wt, has_deadlines=has_deadlines, methodology=methodology
            )
            for wt in work_types
        ]

    primary_concern = ctx.primary_concern
    if not primary_concern:
        pain_words = [
            "struggle", "difficult", "hard to", "problem",
            "issue", "can't", "cannot", "need to",
        ]
        for msg in history:
            if msg.get("role") != "user":
                continue
            for sentence in re.split(r"[.!?]", msg["content"]):
                if any(pw in sentence.lower() for pw in pain_words):
                    primary_concern = sentence.strip()
                    break
            if primary_concern:
                break

    return UserContext(
        company_name=company_name,
        company_size=company_size,
        industry_detail=industry_detail,
        people=people,
        teams=teams,
        work_items=work_items,
        has_remote_teams=has_remote,
        has_clients=has_clients,
        work_methodology=methodology,
        primary_concern=primary_concern,
        key_phrases=key_phrases,
    )


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------


def extract_user_context(state: PreviewGeneratorState) -> dict:
    """Extract structured UserContext from available signals.

    Three-tier resolution — NO redundant LLM call when Dev A's data is present:

    Tier 1 — extraction_result present (Dev A already did the work):
      Map ExtractionResult fields → UserContext directly.
      Keyword scan fills any remaining None fields.
      CONTEXT_EXTRACTION_SYSTEM_PROMPT is NOT invoked.

    Tier 2 — extraction_result absent, history present:
      LLM extraction via CONTEXT_EXTRACTION_SYSTEM_PROMPT (Phase 2, not yet wired).
      Keyword scan fills remaining None fields.
      One LLM call — only for sessions Dev A never processed.

    Tier 3 — nothing available:
      Return empty UserContext(). No LLM call.
    """
    history = state.conversation_history
    extraction_result = state.extraction_result
    preselected_intent = state.preselected_intent

    # --- Tier 1: ExtractionResult present — map directly, no LLM ---
    if extraction_result is not None:
        ctx = _map_extraction_result(extraction_result, preselected_intent)
        ctx = _keyword_fill(ctx, history)
        logger.info(
            "session=%s — Tier 1 context: company=%r size=%r industry=%r "
            "methodology=%r phrases=%d (from ExtractionResult)",
            state.session_id,
            ctx.company_name,
            ctx.company_size,
            ctx.industry_detail,
            ctx.work_methodology,
            len(ctx.key_phrases),
        )
        return {"user_context": ctx}

    # --- Tier 3: no history (and no ExtractionResult) ---
    if not history:
        logger.info(
            "session=%s — Tier 3: no extraction_result and no history, "
            "returning empty UserContext",
            state.session_id,
        )
        return {"user_context": UserContext()}

    # --- Tier 2: no ExtractionResult, but history available ---
    # Phase 2: call _extract_context_via_llm() here using
    # CONTEXT_EXTRACTION_SYSTEM_PROMPT, then pass result to _keyword_fill().
    # For now: keyword-only path (same as original Phase 1 behaviour).
    lower = _user_text(history)
    raw = _raw_user_text(history)

    company_name = _extract_company_name(raw)
    company_size = _detect_company_size(lower)
    _, industry_detail = _detect_industry(lower)
    people = _extract_people(raw)
    teams = _extract_teams(raw, lower)
    work_types = _detect_work_types(lower)
    methodology = _detect_methodology(lower) or _methodology_from_hints(
        [], preselected_intent
    )
    key_phrases = _extract_key_phrases(lower)

    # Append preselected_intent as a signal phrase if it isn't a methodology word
    if preselected_intent:
        intent_lower = preselected_intent.lower()
        is_methodology = any(kw in intent_lower for kw in _METHODOLOGY_HINTS)
        if not is_methodology and preselected_intent not in key_phrases:
            key_phrases.append(preselected_intent)

    has_remote = any(kw in lower for kw in _REMOTE_KEYWORDS)
    has_clients = any(kw in lower for kw in _CLIENT_KEYWORDS)
    has_deadlines = any(
        p in lower for p in ["deadline", "due date", "due by", "by friday"]
    )
    work_items = [
        WorkItemDetail(
            work_type=wt, has_deadlines=has_deadlines, methodology=methodology
        )
        for wt in work_types
    ]

    pain_words = [
        "struggle", "difficult", "hard to", "problem",
        "issue", "can't", "cannot", "need to",
    ]
    primary_concern: str | None = None
    for msg in history:
        if msg.get("role") != "user":
            continue
        for sentence in re.split(r"[.!?]", msg["content"]):
            if any(pw in sentence.lower() for pw in pain_words):
                primary_concern = sentence.strip()
                break
        if primary_concern:
            break

    user_context = UserContext(
        company_name=company_name,
        company_size=company_size,
        industry_detail=industry_detail,
        people=people,
        teams=teams,
        work_items=work_items,
        has_remote_teams=has_remote or None,
        has_clients=has_clients or None,
        work_methodology=methodology,
        primary_concern=primary_concern,
        key_phrases=key_phrases,
    )

    logger.info(
        "session=%s — Tier 2 context: company=%r size=%r industry=%r work_types=%s "
        "(keyword scan — no ExtractionResult)",
        state.session_id,
        company_name,
        company_size,
        industry_detail,
        work_types,
    )
    return {"user_context": user_context}
